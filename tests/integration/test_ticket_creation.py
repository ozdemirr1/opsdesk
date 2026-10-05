from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from queue import Queue
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from opsdesk.config import Settings
from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.repositories.tickets import (
    SqlAlchemyTicketRepository,
    SqlAlchemyTicketTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer
from opsdesk.main import create_app
from opsdesk.tickets.dependencies import (
    get_ticket_creation_service,
)
from opsdesk.tickets.services import TicketCreationService

SECRET = "a" * 64
FIXED_NOW = datetime(2026, 10, 5, 18, 0, tzinfo=UTC)

ACCESS_DENIED_RESPONSE = {
    "error": {
        "code": "organization_access_denied",
        "message": "Organization access denied.",
        "details": [],
    }
}


def build_app(factory):
    return create_app(
        Settings(environment="test"),
        session_factory=factory,
        token_settings=TokenSettings(secret=SECRET),
        token_clock=lambda: FIXED_NOW,
    )


def issue_token(user_id: int) -> str:
    return AccessTokenIssuer(
        TokenSettings(secret=SECRET),
        clock=lambda: FIXED_NOW,
    ).issue(user_id)


def bearer_headers(user_id: int) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {issue_token(user_id)}",
    }


def create_user(
    factory,
    *,
    email: str,
    is_active: bool = True,
) -> int:
    with session_scope(factory) as session:
        user = UserRow(
            email=email,
            password_hash="synthetic-password-hash",
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        return user.user_id


def create_organization_membership(
    factory,
    *,
    user_id: int,
    name: str,
    role: str = "customer",
    organization_is_active: bool = True,
    membership_is_active: bool = True,
) -> tuple[int, int]:
    with session_scope(factory) as session:
        organization = OrganizationRow(
            name=name,
            is_active=organization_is_active,
        )
        session.add(organization)
        session.flush()

        membership = OrganizationMembershipRow(
            user_id=user_id,
            organization_id=organization.organization_id,
            role=role,
            is_active=membership_is_active,
        )
        session.add(membership)
        session.commit()

        return (
            organization.organization_id,
            membership.membership_id,
        )


def ticket_count(factory) -> int:
    with session_scope(factory) as session:
        return session.scalar(select(func.count()).select_from(TicketRow))


@pytest.mark.integration
@pytest.mark.parametrize(
    ("role", "supplied_priority", "expected_priority"),
    [
        ("customer", None, "medium"),
        ("agent", "low", "low"),
        ("admin", "high", "high"),
        ("owner", "urgent", "urgent"),
    ],
)
def test_each_role_creates_durable_self_attributed_ticket(
    identity_scope,
    role,
    supplied_priority,
    expected_priority,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email=f"ticket-{role}@example.com",
        )
        organization_id, membership_id = create_organization_membership(
            factory,
            user_id=actor_id,
            name=f"{role.title()} Organization",
            role=role,
        )

        payload = {
            "title": "  Login problem  ",
            "description": (
                "  Traceback:\n    Connection refused\n  Please investigate.  "
            ),
        }

        if supplied_priority is not None:
            payload["priority"] = supplied_priority

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                f"/organizations/{organization_id}/tickets",
                json=payload,
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 201
        response_payload = response.json()
        ticket_id = response_payload["ticket_id"]

        assert response_payload == {
            "ticket_id": ticket_id,
            "organization_id": organization_id,
            "requester_membership_id": membership_id,
            "creator_membership_id": membership_id,
            "assignee_membership_id": None,
            "title": "Login problem",
            "description": (
                "Traceback:\n    Connection refused\n  Please investigate."
            ),
            "status": "open",
            "priority": expected_priority,
            "created_at": response_payload["created_at"],
            "updated_at": response_payload["updated_at"],
        }
        assert response_payload["created_at"] == response_payload["updated_at"]
        assert "password" not in response.text

        with session_scope(factory) as verification_session:
            stored = verification_session.get(
                TicketRow,
                ticket_id,
            )

            assert stored is not None
            assert stored.organization_id == organization_id
            assert stored.requester_membership_id == membership_id
            assert stored.creator_membership_id == membership_id
            assert stored.assignee_membership_id is None
            assert stored.title == "Login problem"
            assert stored.description == (
                "Traceback:\n    Connection refused\n  Please investigate."
            )
            assert stored.status == "open"
            assert stored.priority == expected_priority
            assert stored.created_at == stored.updated_at

            serialized_created_at = datetime.fromisoformat(
                response_payload["created_at"].replace(
                    "Z",
                    "+00:00",
                )
            )
            assert serialized_created_at == stored.created_at

        assert ticket_count(factory) == 1


@pytest.mark.integration
def test_missing_foreign_and_inactive_membership_create_no_ticket(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="denied-ticket-actor@example.com",
        )
        foreign_user_id = create_user(
            factory,
            email="foreign-ticket-owner@example.com",
        )

        foreign_organization_id, _ = create_organization_membership(
            factory,
            user_id=foreign_user_id,
            name="Foreign Organization",
        )
        inactive_organization_id, _ = create_organization_membership(
            factory,
            user_id=actor_id,
            name="Inactive Membership Organization",
            membership_is_active=False,
        )

        app = build_app(factory)
        payload = {
            "title": "Login problem",
            "description": "Login is unavailable.",
        }

        with TestClient(app) as client:
            responses = [
                client.post(
                    "/organizations/9223372036854775807/tickets",
                    json=payload,
                    headers=bearer_headers(actor_id),
                ),
                client.post(
                    (f"/organizations/{foreign_organization_id}/tickets"),
                    json=payload,
                    headers=bearer_headers(actor_id),
                ),
                client.post(
                    (f"/organizations/{inactive_organization_id}/tickets"),
                    json=payload,
                    headers=bearer_headers(actor_id),
                ),
            ]

        for response in responses:
            assert response.status_code == 403
            assert response.json() == ACCESS_DENIED_RESPONSE

        assert ticket_count(factory) == 0


@pytest.mark.integration
def test_suspended_organization_returns_specific_403_without_ticket(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="suspended-ticket-actor@example.com",
        )
        organization_id, _ = create_organization_membership(
            factory,
            user_id=actor_id,
            name="Suspended Organization",
            organization_is_active=False,
        )

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                f"/organizations/{organization_id}/tickets",
                json={
                    "title": "Login problem",
                    "description": "Login is unavailable.",
                },
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 403
        assert response.json() == {
            "error": {
                "code": "organization_suspended",
                "message": "Organization is suspended.",
                "details": [],
            }
        }
        assert ticket_count(factory) == 0


@pytest.mark.integration
def test_inactive_user_returns_401_without_ticket(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="inactive-ticket-actor@example.com",
            is_active=False,
        )
        organization_id, _ = create_organization_membership(
            factory,
            user_id=actor_id,
            name="Inactive User Organization",
        )

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                f"/organizations/{organization_id}/tickets",
                json={
                    "title": "Login problem",
                    "description": "Login is unavailable.",
                },
                headers=bearer_headers(actor_id),
            )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"]["code"] == "unauthenticated"
        assert ticket_count(factory) == 0


class FailingCommitTransaction:
    def __init__(self, session) -> None:
        self._session = session
        self.commit_called = False
        self.rollback_called = False

    def commit(self) -> None:
        self.commit_called = True
        raise RuntimeError("Synthetic ticket commit failure")

    def rollback(self) -> None:
        self.rollback_called = True
        self._session.rollback()


@pytest.mark.integration
def test_commit_failure_rolls_back_flushed_ticket(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="ticket-commit-failure@example.com",
        )
        organization_id, _ = create_organization_membership(
            factory,
            user_id=actor_id,
            name="Rollback Organization",
        )

        with session_scope(factory) as creation_session:
            transaction = FailingCommitTransaction(creation_session)
            service = TicketCreationService(
                repository=SqlAlchemyTicketRepository(creation_session),
                transaction=transaction,
            )

            with pytest.raises(
                RuntimeError,
                match="^Synthetic ticket commit failure$",
            ):
                service.create(
                    actor_user_id=actor_id,
                    organization_id=organization_id,
                    title="Must roll back",
                    description="No Ticket may remain.",
                    priority="medium",
                )

            assert transaction.commit_called is True
            assert transaction.rollback_called is True

        assert ticket_count(factory) == 0


@pytest.mark.integration
def test_unknown_constraint_failure_is_not_mapped_to_busy(
    identity_scope,
):
    with identity_scope() as factory:
        actor_id = create_user(
            factory,
            email="ticket-constraint-failure@example.com",
        )
        organization_id, _ = create_organization_membership(
            factory,
            user_id=actor_id,
            name="Constraint Organization",
        )

        with session_scope(factory) as creation_session:
            service = TicketCreationService(
                repository=SqlAlchemyTicketRepository(creation_session),
                transaction=SqlAlchemyTicketTransaction(creation_session),
            )

            with pytest.raises(IntegrityError) as exc_info:
                service.create(
                    actor_user_id=actor_id,
                    organization_id=organization_id,
                    title="",
                    description="Invalid direct service input.",
                    priority="medium",
                )

        assert exc_info.value.orig.diag.constraint_name == "ck_tickets_title_length"
        assert ticket_count(factory) == 0


def wait_for_database_blocker(
    factory,
    *,
    worker_pid: int,
    expected_blocker_pid: int,
) -> list[int]:
    deadline = monotonic() + 5

    with session_scope(factory) as observer_session:
        while monotonic() < deadline:
            blocker_pids = observer_session.scalar(
                text("SELECT pg_blocking_pids(CAST(:worker_pid AS integer))"),
                {
                    "worker_pid": worker_pid,
                },
            )

            if expected_blocker_pid in blocker_pids:
                return blocker_pids

            sleep(0.05)

    raise AssertionError(
        "Ticket creation was not observed waiting on the expected Organization lock."
    )


@pytest.mark.integration
def test_organization_lock_timeout_is_503_while_other_org_progresses(
    identity_scope,
):
    worker_pids: Queue[int] = Queue()

    with identity_scope() as factory:
        blocked_user_id = create_user(
            factory,
            email="blocked-ticket-actor@example.com",
        )
        blocked_organization_id, _ = create_organization_membership(
            factory,
            user_id=blocked_user_id,
            name="Blocked Ticket Organization",
        )

        independent_user_id = create_user(
            factory,
            email="independent-ticket-actor@example.com",
        )
        independent_organization_id, _ = create_organization_membership(
            factory,
            user_id=independent_user_id,
            name="Independent Ticket Organization",
        )

        def get_observed_ticket_creation_service():
            with session_scope(factory) as session:
                worker_pid = session.scalar(text("SELECT pg_backend_pid()"))
                worker_pids.put(worker_pid)

                yield TicketCreationService(
                    repository=SqlAlchemyTicketRepository(session),
                    transaction=SqlAlchemyTicketTransaction(session),
                )

        app = build_app(factory)
        app.dependency_overrides[get_ticket_creation_service] = (
            get_observed_ticket_creation_service
        )

        with TestClient(app) as client:
            with session_scope(factory) as blocker_session:
                blocker_pid = blocker_session.scalar(text("SELECT pg_backend_pid()"))

                locked_organization = blocker_session.scalar(
                    select(OrganizationRow)
                    .where(OrganizationRow.organization_id == blocked_organization_id)
                    .with_for_update()
                )

                assert locked_organization is not None

                with ThreadPoolExecutor(max_workers=1) as executor:
                    blocked_future = executor.submit(
                        client.post,
                        (f"/organizations/{blocked_organization_id}/tickets"),
                        json={
                            "title": "Blocked ticket",
                            "description": ("This request must time out."),
                        },
                        headers=bearer_headers(blocked_user_id),
                    )

                    worker_pid = worker_pids.get(timeout=5)

                    blockers = wait_for_database_blocker(
                        factory,
                        worker_pid=worker_pid,
                        expected_blocker_pid=blocker_pid,
                    )

                    assert blocker_pid in blockers

                    independent_response = client.post(
                        (f"/organizations/{independent_organization_id}/tickets"),
                        json={
                            "title": "Independent ticket",
                            "description": ("This request must succeed."),
                        },
                        headers=bearer_headers(independent_user_id),
                    )

                    blocked_response = blocked_future.result(timeout=10)

                blocker_session.rollback()

        assert independent_response.status_code == 201
        assert independent_response.json()["title"] == "Independent ticket"

        assert blocked_response.status_code == 503
        assert blocked_response.json() == {
            "error": {
                "code": "concurrency_busy",
                "message": ("The operation is temporarily busy. Please try again."),
                "details": [],
            }
        }
        assert "retry-after" not in blocked_response.headers

        with session_scope(factory) as verification_session:
            tickets = verification_session.scalars(
                select(TicketRow).order_by(TicketRow.ticket_id)
            ).all()

            assert len(tickets) == 1
            assert tickets[0].organization_id == independent_organization_id
            assert (
                tickets[0].requester_membership_id == tickets[0].creator_membership_id
            )
            assert tickets[0].title == "Independent ticket"

        assert ticket_count(factory) == 1
