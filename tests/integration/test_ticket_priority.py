from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import UTC, datetime
from queue import Queue

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from tests.integration import test_comments
from tests.integration.test_ticket_creation import (
    bearer_headers,
    build_app,
    wait_for_database_blocker,
)

from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.repositories.ticket_priority import (
    SqlAlchemyTicketPriorityRepository,
    ticket_value,
)
from opsdesk.db.repositories.tickets import SqlAlchemyTicketTransaction
from opsdesk.db.session import session_scope
from opsdesk.tickets.priority import PriorityBusyError, TicketPriorityService

context = test_comments.context
pytestmark = pytest.mark.integration
OLD = datetime(2020, 1, 1, tzinfo=UTC)


def setup_role(factory, data, role="agent", status="open"):
    with session_scope(factory) as session:
        session.execute(
            update(OrganizationMembershipRow)
            .where(OrganizationMembershipRow.membership_id == data["members"][0])
            .values(role=role)
        )
        session.execute(
            update(TicketRow)
            .where(TicketRow.ticket_id == data["tickets"][0])
            .values(status=status, updated_at=OLD)
        )
        session.commit()


def value(factory, data):
    with session_scope(factory) as session:
        return ticket_value(session.get(TicketRow, data["tickets"][0]))


def args(data, i=0):
    return dict(
        actor_user_id=data["users"][i],
        organization_id=data["orgs"][0],
        ticket_id=data["tickets"][0],
        priority="high",
    )


def service(session, tx=None):
    return TicketPriorityService(
        SqlAlchemyTicketPriorityRepository(session),
        tx or SqlAlchemyTicketTransaction(session),
    )


def path(data, org=None, ticket=None):
    return f"/organizations/{org or data['orgs'][0]}/tickets/{ticket or data['tickets'][0]}/priority"


@pytest.mark.parametrize("role", ["customer", "agent", "admin", "owner"])
@pytest.mark.parametrize("state", ["open", "in_progress", "resolved", "closed"])
@pytest.mark.parametrize("same", [False, True])
def test_role_state_noop_matrix_and_durable_timestamps(context, role, state, same):
    factory, data = context
    setup_role(factory, data, role, state)
    before = value(factory, data)
    with TestClient(build_app(factory)) as client:
        response = client.put(
            path(data),
            json={"priority": "medium" if same else "high"},
            headers=bearer_headers(data["users"][0]),
        )
    expected = (
        403 if role == "customer" else 409 if state in ("resolved", "closed") else 200
    )
    assert response.status_code == expected
    after = value(factory, data)
    if expected != 200 or same:
        assert after == before
    else:
        assert after.priority == "high" and after.updated_at > before.updated_at
        assert {
            k: v
            for k, v in asdict(after).items()
            if k not in ("priority", "updated_at")
        } == {
            k: v
            for k, v in asdict(before).items()
            if k not in ("priority", "updated_at")
        }
        assert response.json()["updated_at"] == after.updated_at.isoformat().replace(
            "+00:00", "Z"
        )


@pytest.mark.parametrize(
    "case,status",
    [
        ("foreign_org", 403),
        ("foreign_ticket", 404),
        ("hidden", 404),
        ("missing", 404),
        ("user", 401),
        ("membership", 403),
        ("organization", 403),
    ],
)
def test_denials_leave_ticket_unchanged(context, case, status):
    factory, data = context
    setup_role(factory, data)
    target = path(data)
    actor = data["users"][0]
    if case == "foreign_org":
        target = path(data, org=data["orgs"][1], ticket=data["tickets"][2])
    if case == "foreign_ticket":
        target = path(data, ticket=data["tickets"][2])
    if case == "hidden":
        actor = data["users"][1]
    if case == "missing":
        target = path(data, ticket=9223372036854775807)
    if case in ("user", "membership", "organization"):
        model, column, pk = {
            "user": (UserRow, UserRow.user_id, data["users"][0]),
            "membership": (
                OrganizationMembershipRow,
                OrganizationMembershipRow.membership_id,
                data["members"][0],
            ),
            "organization": (
                OrganizationRow,
                OrganizationRow.organization_id,
                data["orgs"][0],
            ),
        }[case]
        with session_scope(factory) as session:
            session.execute(update(model).where(column == pk).values(is_active=False))
            session.commit()
    before = value(factory, data)
    with TestClient(build_app(factory)) as client:
        assert (
            client.put(
                target, json={"priority": "high"}, headers=bearer_headers(actor)
            ).status_code
            == status
        )
    assert value(factory, data) == before


def test_commit_failure_rolls_back_field_and_timestamp(context):
    factory, data = context
    setup_role(factory, data)
    before = value(factory, data)
    with session_scope(factory) as session:

        class FailCommit(SqlAlchemyTicketTransaction):
            def commit(self):
                assert session.get(TicketRow, data["tickets"][0]).priority == "high"
                raise RuntimeError("Synthetic failure")

        with pytest.raises(RuntimeError):
            service(session, FailCommit(session)).change(**args(data))
    assert value(factory, data) == before


@pytest.mark.parametrize(
    "mutation,status", [("close", 409), ("demote", 403), ("deactivate", 403)]
)
def test_waiter_rechecks_state_and_role_after_cooperating_change(
    context, mutation, status
):
    factory, data = context
    setup_role(factory, data)
    pids = Queue()
    with session_scope(factory) as first:
        first_pid = first.scalar(text("SELECT pg_backend_pid()"))
        SqlAlchemyTicketPriorityRepository(first).lock_context(
            **{k: v for k, v in args(data).items() if k != "priority"}
        )
        if mutation == "close":
            first.execute(
                update(TicketRow)
                .where(TicketRow.ticket_id == data["tickets"][0])
                .values(status="closed")
            )
        else:
            first.execute(
                update(OrganizationMembershipRow)
                .where(OrganizationMembershipRow.membership_id == data["members"][0])
                .values(
                    **(
                        {"role": "customer"}
                        if mutation == "demote"
                        else {"is_active": False}
                    )
                )
            )
        app = build_app(factory)
        from opsdesk.tickets.dependencies import get_ticket_priority_service

        def observed():
            with session_scope(factory) as session:
                stale = session.get(TicketRow, data["tickets"][0])
                assert stale.status == "open"
                pids.put(session.scalar(text("SELECT pg_backend_pid()")))
                yield service(session)

        app.dependency_overrides[get_ticket_priority_service] = observed
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                client.put,
                path(data),
                json={"priority": "high"},
                headers=bearer_headers(data["users"][0]),
            )
            try:
                wait_for_database_blocker(
                    factory,
                    worker_pid=pids.get(timeout=5),
                    expected_blocker_pid=first_pid,
                )
                first.commit()
            finally:
                first.rollback()
            assert future.result(timeout=10).status_code == status
    result = value(factory, data)
    assert result.priority == "medium" and result.updated_at == OLD


def test_lock_timeout_has_no_write(context):
    factory, data = context
    setup_role(factory, data)
    before = value(factory, data)
    with session_scope(factory) as blocker:
        blocker.scalar(
            select(OrganizationRow)
            .where(OrganizationRow.organization_id == data["orgs"][0])
            .with_for_update()
        )
        with session_scope(factory) as session:
            with pytest.raises(PriorityBusyError):
                service(session).change(**args(data))
            assert not session.in_transaction()
        blocker.rollback()
    assert value(factory, data) == before
