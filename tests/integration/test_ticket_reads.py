from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, update

from opsdesk.config import Settings
from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.repositories.ticket_reads import SqlAlchemyTicketReadRepository
from opsdesk.db.session import session_scope
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer
from opsdesk.main import create_app
from opsdesk.tickets.read_models import TicketFilters
from opsdesk.tickets.services import TicketActorUnavailableError, TicketReadService

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)
SECRET = "read-integration-test-secret-" * 3


def seed(factory, role="customer"):
    with session_scope(factory) as session:
        users = [
            UserRow(
                email=f"read-{i}@example.com",
                password_hash="synthetic-hash",
                is_active=True,
            )
            for i in range(3)
        ]
        orgs = [OrganizationRow(name=f"Read {i}", is_active=True) for i in range(2)]
        session.add_all(users + orgs)
        session.flush()
        memberships = [
            OrganizationMembershipRow(
                user_id=users[0].user_id,
                organization_id=orgs[0].organization_id,
                role=role,
                is_active=True,
            ),
            OrganizationMembershipRow(
                user_id=users[1].user_id,
                organization_id=orgs[0].organization_id,
                role="customer",
                is_active=True,
            ),
            OrganizationMembershipRow(
                user_id=users[2].user_id,
                organization_id=orgs[1].organization_id,
                role="owner",
                is_active=True,
            ),
            OrganizationMembershipRow(
                user_id=users[0].user_id,
                organization_id=orgs[1].organization_id,
                role="customer",
                is_active=True,
            ),
        ]
        session.add_all(memberships)
        session.commit()
        return {
            "user": users[0].user_id,
            "other_user": users[1].user_id,
            "org": orgs[0].organization_id,
            "foreign_org": orgs[1].organization_id,
            "mine": memberships[0].membership_id,
            "other": memberships[1].membership_id,
            "foreign": memberships[2].membership_id,
            "foreign_mine": memberships[3].membership_id,
        }


def add_ticket(factory, data, *, foreign=False, requester=None, **overrides):
    values = dict(
        organization_id=data["foreign_org"] if foreign else data["org"],
        requester_membership_id=requester
        or (data["foreign"] if foreign else data["mine"]),
        creator_membership_id=data["foreign"] if foreign else data["mine"],
        title="Access problem",
        description="Line one.\nLine two.",
        status="open",
        priority="medium",
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(overrides)
    with session_scope(factory) as session:
        row = TicketRow(**values)
        session.add(row)
        session.commit()
        return row.ticket_id


def client_for(factory, actor):
    tokens = TokenSettings(secret=SECRET)
    app = create_app(
        Settings(environment="test"),
        session_factory=factory,
        token_settings=tokens,
        token_clock=lambda: NOW,
    )
    token = AccessTokenIssuer(tokens, clock=lambda: NOW).issue(actor)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def path(data, ticket_id=None, foreign=False):
    org = data["foreign_org"] if foreign else data["org"]
    return f"/organizations/{org}/tickets" + (
        f"/{ticket_id}" if ticket_id is not None else ""
    )


def snapshot(factory):
    with session_scope(factory) as session:
        return [
            tuple(
                session.execute(
                    select(*model.__table__.c).order_by(*model.__table__.primary_key)
                ).all()
            )
            for model in (
                UserRow,
                OrganizationRow,
                OrganizationMembershipRow,
                TicketRow,
            )
        ]


def test_customer_scope_applies_before_count_page_and_detail_without_writes(
    identity_scope,
):
    with identity_scope() as factory:
        data = seed(factory)
        mine = add_ticket(factory, data)
        hidden = add_ticket(factory, data, requester=data["other"])
        foreign = add_ticket(factory, data, foreign=True)
        before = snapshot(factory)
        with client_for(factory, data["user"]) as client:
            response = client.get(path(data), params={"limit": 1})
            assert response.status_code == 200
            assert response.json()["total_count"] == 1
            assert [t["ticket_id"] for t in response.json()["items"]] == [mine]
            detail = client.get(path(data, mine))
            assert detail.status_code == 200
            assert detail.json()["description"] == "Line one.\nLine two."
            denied = [
                client.get(path(data, id))
                for id in (hidden, foreign, 9223372036854775807)
            ]
            assert all(r.status_code == 404 for r in denied)
            assert all(r.json() == denied[0].json() for r in denied)
            assert denied[0].json()["error"]["code"] == "ticket_not_found"
            assert client.get(path(data), params={"offset": 10}).json() == dict(
                items=[], total_count=1, limit=20, offset=10
            )
        assert snapshot(factory) == before


@pytest.mark.parametrize("role", ["agent", "admin", "owner"])
def test_staff_can_read_all_in_org_but_customer_role_in_other_org_still_limits(
    identity_scope, role
):
    with identity_scope() as factory:
        data = seed(factory, role)
        own = add_ticket(factory, data)
        other = add_ticket(factory, data, requester=data["other"])
        foreign = add_ticket(factory, data, foreign=True)
        with client_for(factory, data["user"]) as client:
            response = client.get(path(data))
            assert response.status_code == 200
            assert [t["ticket_id"] for t in response.json()["items"]] == [other, own]
            assert client.get(path(data, other)).status_code == 200
            assert client.get(path(data, foreign)).status_code == 404
            assert client.get(path(data, foreign=True)).json()["total_count"] == 0
            assert client.get(path(data, foreign, foreign=True)).status_code == 404


@pytest.mark.parametrize(
    "kind,code,status",
    [
        ("user", "unauthenticated", 401),
        ("membership", "organization_access_denied", 403),
        ("organization", "organization_suspended", 403),
        ("both", "organization_access_denied", 403),
        ("missing_org", "organization_access_denied", 403),
    ],
)
def test_access_errors_do_not_disclose_ticket_existence(
    identity_scope, kind, code, status
):
    with identity_scope() as factory:
        data = seed(factory)
        ticket = add_ticket(factory, data)
        with session_scope(factory) as session:
            if kind == "user":
                session.execute(
                    update(UserRow)
                    .where(UserRow.user_id == data["user"])
                    .values(is_active=False)
                )
            if kind in ("membership", "both"):
                session.execute(
                    update(OrganizationMembershipRow)
                    .where(OrganizationMembershipRow.membership_id == data["mine"])
                    .values(is_active=False)
                )
            if kind in ("organization", "both"):
                session.execute(
                    update(OrganizationRow)
                    .where(OrganizationRow.organization_id == data["org"])
                    .values(is_active=False)
                )
            session.commit()
        if kind == "missing_org":
            data["org"] = 9223372036854775807
        with client_for(factory, data["user"]) as client:
            for target in (
                path(data),
                path(data, ticket),
                path(data, 9223372036854775807),
            ):
                response = client.get(target)
                assert response.status_code == status
                assert response.json()["error"]["code"] == code
                assert response.json()["error"]["details"] == []


def test_pagination_has_deterministic_ties_and_empty_pages_keep_total(identity_scope):
    with identity_scope() as factory:
        data = seed(factory, "agent")
        older = add_ticket(factory, data, created_at=NOW - timedelta(days=1))
        middle = add_ticket(factory, data)
        newest = add_ticket(factory, data)
        with client_for(factory, data["user"]) as client:
            first = client.get(path(data), params={"limit": 2}).json()
            second = client.get(path(data), params={"limit": 2, "offset": 2}).json()
            assert [t["ticket_id"] for t in first["items"]] == [newest, middle]
            assert [t["ticket_id"] for t in second["items"]] == [older]
            assert first["total_count"] == second["total_count"] == 3
            assert (
                client.get(path(data), params={"offset": 9223372036854775807}).json()[
                    "total_count"
                ]
                == 3
            )
            empty = client.get(path(data), params={"q": "not present"}).json()
            assert empty == dict(items=[], total_count=0, limit=20, offset=0)


def test_literal_search_case_and_combined_filters_in_postgres(identity_scope):
    with identity_scope() as factory:
        data = seed(factory, "agent")
        special = add_ticket(
            factory,
            data,
            title="Disk 100%_! \\ path é",
            status="closed",
            priority="urgent",
            assignee_membership_id=data["mine"],
        )
        add_ticket(factory, data, title="Disk 100xxx path e", requester=data["other"])
        percent_encoded = add_ticket(factory, data, title="literal %25 token")
        with client_for(factory, data["user"]) as client:
            for query in ("100%_!", "\\", "é", "  DISK 100%_!  "):
                result = client.get(path(data), params={"q": query})
                assert result.status_code == 200
                assert [t["ticket_id"] for t in result.json()["items"]] == [special]
            assert (
                client.get(path(data), params={"q": "e\u0301"}).json()["total_count"]
                == 0
            )
            assert [
                t["ticket_id"]
                for t in client.get(path(data), params={"q": "%25"}).json()["items"]
            ] == [percent_encoded]
            filters = dict(
                q="disk",
                status="closed",
                priority="urgent",
                assignment="assigned",
                assignee_membership_id=data["mine"],
            )
            result = client.get(path(data), params=filters).json()
            assert result["total_count"] == 1
            assert result["items"][0]["ticket_id"] == special
            assert (
                client.get(path(data), params={"assignment": "unassigned"}).json()[
                    "total_count"
                ]
                == 2
            )
            assert (
                client.get(
                    path(data), params={"assignee_membership_id": data["foreign"]}
                ).json()["total_count"]
                == 0
            )


@pytest.mark.parametrize("status", ["open", "in_progress", "resolved", "closed"])
def test_all_ticket_states_remain_readable(identity_scope, status):
    with identity_scope() as factory:
        data = seed(factory)
        ticket = add_ticket(factory, data, status=status)
        with client_for(factory, data["user"]) as client:
            assert client.get(path(data, ticket)).json()["status"] == status
            assert (
                client.get(path(data), params={"status": status}).json()["total_count"]
                == 1
            )


def test_one_statement_keeps_count_and_page_consistent_during_insert(
    identity_scope, integration_engine
):
    with identity_scope() as factory:
        data = seed(factory)
        original = add_ticket(factory, data)
        inserted = []

        def insert_after_read(
            connection, cursor, statement, parameters, context, executemany
        ):
            if "ticket_page AS" in statement and not inserted:
                inserted.append(add_ticket(factory, data))

        event.listen(integration_engine, "after_cursor_execute", insert_after_read)
        try:
            with session_scope(factory) as session:
                repo = SqlAlchemyTicketReadRepository(session)
                page = repo.list_for_actor(
                    actor_user_id=data["user"],
                    organization_id=data["org"],
                    filters=TicketFilters(),
                    limit=20,
                    offset=0,
                ).page
                assert inserted
                assert page.total_count == len(page.items) == 1
                assert page.items[0].ticket_id == original
        finally:
            event.remove(integration_engine, "after_cursor_execute", insert_after_read)
        with client_for(factory, data["user"]) as client:
            assert client.get(path(data)).json()["total_count"] == 2


def test_read_rechecks_user_after_authentication_snapshot(identity_scope):
    with identity_scope() as factory:
        data = seed(factory)
        add_ticket(factory, data)
        with session_scope(factory) as stale_session:
            authenticated_user = stale_session.get(UserRow, data["user"])
            assert authenticated_user.is_active
            with session_scope(factory) as revocation:
                revocation.execute(
                    update(UserRow)
                    .where(UserRow.user_id == data["user"])
                    .values(is_active=False)
                )
                revocation.commit()
            service = TicketReadService(SqlAlchemyTicketReadRepository(stale_session))
            with pytest.raises(TicketActorUnavailableError):
                service.list_for_actor(
                    actor_user_id=data["user"],
                    organization_id=data["org"],
                    filters=TicketFilters(),
                    limit=20,
                    offset=0,
                )


def test_search_is_title_only_and_apostrophes_are_bound_literals(identity_scope):
    with identity_scope() as factory:
        data = seed(factory)
        literal = add_ticket(factory, data, title="Customer's ' OR 1=1 -- request")
        add_ticket(
            factory,
            data,
            title="Another issue",
            description="Customer's ' OR 1=1 -- request",
        )
        hidden = add_ticket(
            factory,
            data,
            title="Customer's ' OR 1=1 -- request",
            requester=data["other"],
            assignee_membership_id=data["mine"],
        )
        with client_for(factory, data["user"]) as client:
            response = client.get(path(data), params={"q": "' OR 1=1 --"})
            assert response.status_code == 200
            assert response.json()["total_count"] == 1
            assert [t["ticket_id"] for t in response.json()["items"]] == [literal]
            assert client.get(path(data, hidden)).status_code == 404


@pytest.mark.parametrize("change", ["membership", "organization", "role"])
def test_read_uses_current_access_despite_preloaded_membership(identity_scope, change):
    with identity_scope() as factory:
        data = seed(factory, "agent")
        own = add_ticket(factory, data)
        add_ticket(factory, data, requester=data["other"])
        with session_scope(factory) as session:
            old_membership = session.get(OrganizationMembershipRow, data["mine"])
            assert old_membership.role == "agent"
            with session_scope(factory) as writer:
                if change == "organization":
                    writer.execute(
                        update(OrganizationRow)
                        .where(OrganizationRow.organization_id == data["org"])
                        .values(is_active=False)
                    )
                else:
                    values = (
                        {"role": "customer"}
                        if change == "role"
                        else {"is_active": False}
                    )
                    writer.execute(
                        update(OrganizationMembershipRow)
                        .where(OrganizationMembershipRow.membership_id == data["mine"])
                        .values(**values)
                    )
                writer.commit()
            read = SqlAlchemyTicketReadRepository(session).list_for_actor(
                actor_user_id=data["user"],
                organization_id=data["org"],
                filters=TicketFilters(),
                limit=20,
                offset=0,
            )
            if change == "role":
                assert read.page.total_count == 1
                assert [t.ticket_id for t in read.page.items] == [own]
            else:
                assert read.page.total_count == 0
                assert read.page.items == ()
                assert not (
                    read.access.membership_active
                    if change == "membership"
                    else read.access.organization_active
                )
