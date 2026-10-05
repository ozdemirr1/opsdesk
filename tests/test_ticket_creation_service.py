from datetime import UTC, datetime

import pytest

from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    Organization,
    OrganizationMembership,
)
from opsdesk.tickets.models import (
    NewTicket,
    Ticket,
    TicketCreationContext,
)
from opsdesk.tickets.repositories import TicketConcurrencyError
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketCreationBusyError,
    TicketCreationService,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)

FIXED_TIME = datetime(2026, 10, 5, 15, 0, tzinfo=UTC)


def build_context(
    *,
    role: str = "customer",
    organization_active: bool = True,
    actor_present: bool = True,
    actor_active: bool = True,
    membership_present: bool = True,
    membership_active: bool = True,
) -> TicketCreationContext:
    actor = (
        User(
            user_id=42,
            email="actor@example.com",
            password_hash="synthetic-password-hash",
            is_active=actor_active,
        )
        if actor_present
        else None
    )

    membership = (
        OrganizationMembership(
            membership_id=200,
            user_id=42,
            organization_id=100,
            role=role,
            is_active=membership_active,
        )
        if membership_present
        else None
    )

    return TicketCreationContext(
        organization=Organization(
            organization_id=100,
            name="Acme",
            is_active=organization_active,
        ),
        actor_user=actor,
        actor_membership=membership,
    )


class FakeTicketRepository:
    def __init__(
        self,
        events: list[str],
        context: TicketCreationContext | None,
        *,
        fail_at: str | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.events = events
        self.context = context
        self.fail_at = fail_at
        self.failure = failure
        self.received_new_ticket: NewTicket | None = None

    def _raise_if_requested(self, step: str) -> None:
        if self.fail_at == step:
            if self.failure is not None:
                raise self.failure
            raise RuntimeError(f"Synthetic {step} failure")

    def lock_creation_context(
        self,
        *,
        organization_id: int,
        actor_user_id: int,
    ) -> TicketCreationContext | None:
        self.events.append("lock_context")
        assert organization_id == 100
        assert actor_user_id == 42
        self._raise_if_requested("lock_context")
        return self.context

    def create(self, new_ticket: NewTicket) -> Ticket:
        self.events.append("create")
        self.received_new_ticket = new_ticket
        self._raise_if_requested("create")

        return Ticket(
            ticket_id=300,
            organization_id=new_ticket.organization_id,
            requester_membership_id=(new_ticket.requester_membership_id),
            creator_membership_id=(new_ticket.creator_membership_id),
            assignee_membership_id=None,
            title=new_ticket.title,
            description=new_ticket.description,
            status="open",
            priority=new_ticket.priority,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )


class FakeTransaction:
    def __init__(
        self,
        events: list[str],
        *,
        failure: Exception | None = None,
    ) -> None:
        self.events = events
        self.failure = failure

    def commit(self) -> None:
        self.events.append("commit")

        if self.failure is not None:
            raise self.failure

    def rollback(self) -> None:
        self.events.append("rollback")


@pytest.mark.parametrize(
    "role",
    [
        "owner",
        "admin",
        "agent",
        "customer",
    ],
)
def test_all_roles_create_self_attributed_open_unassigned_ticket(
    role,
):
    events: list[str] = []
    repository = FakeTicketRepository(
        events,
        build_context(role=role),
    )
    transaction = FakeTransaction(events)
    service = TicketCreationService(repository, transaction)

    ticket = service.create(
        actor_user_id=42,
        organization_id=100,
        title="Login problem",
        description="Login is unavailable.",
        priority="high",
    )

    assert repository.received_new_ticket == NewTicket(
        organization_id=100,
        requester_membership_id=200,
        creator_membership_id=200,
        title="Login problem",
        description="Login is unavailable.",
        priority="high",
    )
    assert ticket.status == "open"
    assert ticket.assignee_membership_id is None
    assert events == [
        "lock_context",
        "create",
        "commit",
    ]


@pytest.mark.parametrize(
    ("context", "expected_error"),
    [
        (
            None,
            TicketOrganizationAccessDeniedError,
        ),
        (
            build_context(actor_present=False),
            TicketActorUnavailableError,
        ),
        (
            build_context(actor_active=False),
            TicketActorUnavailableError,
        ),
        (
            build_context(membership_present=False),
            TicketOrganizationAccessDeniedError,
        ),
        (
            build_context(membership_active=False),
            TicketOrganizationAccessDeniedError,
        ),
        (
            build_context(organization_active=False),
            TicketOrganizationSuspendedError,
        ),
        (
            build_context(
                organization_active=False,
                membership_active=False,
            ),
            TicketOrganizationAccessDeniedError,
        ),
    ],
)
def test_rejected_context_rolls_back_without_ticket(
    context,
    expected_error,
):
    events: list[str] = []
    repository = FakeTicketRepository(events, context)
    transaction = FakeTransaction(events)
    service = TicketCreationService(repository, transaction)

    with pytest.raises(expected_error):
        service.create(
            actor_user_id=42,
            organization_id=100,
            title="Login problem",
            description="Login is unavailable.",
            priority="medium",
        )

    assert repository.received_new_ticket is None
    assert events == [
        "lock_context",
        "rollback",
    ]


@pytest.mark.parametrize(
    ("fail_at", "commit_failure", "expected_events"),
    [
        (
            "lock_context",
            None,
            ["lock_context", "rollback"],
        ),
        (
            "create",
            None,
            ["lock_context", "create", "rollback"],
        ),
        (
            None,
            TicketConcurrencyError(),
            [
                "lock_context",
                "create",
                "commit",
                "rollback",
            ],
        ),
    ],
)
def test_concurrency_failure_becomes_busy_error(
    fail_at,
    commit_failure,
    expected_events,
):
    events: list[str] = []
    repository = FakeTicketRepository(
        events,
        build_context(),
        fail_at=fail_at,
        failure=(TicketConcurrencyError() if fail_at is not None else None),
    )
    transaction = FakeTransaction(
        events,
        failure=commit_failure,
    )
    service = TicketCreationService(repository, transaction)

    with pytest.raises(TicketCreationBusyError):
        service.create(
            actor_user_id=42,
            organization_id=100,
            title="Login problem",
            description="Login is unavailable.",
            priority="medium",
        )

    assert events == expected_events


@pytest.mark.parametrize(
    ("fail_at", "commit_failure", "expected_events"),
    [
        (
            "lock_context",
            None,
            ["lock_context", "rollback"],
        ),
        (
            "create",
            None,
            ["lock_context", "create", "rollback"],
        ),
        (
            None,
            RuntimeError("Synthetic commit failure"),
            [
                "lock_context",
                "create",
                "commit",
                "rollback",
            ],
        ),
    ],
)
def test_unknown_failure_rolls_back_and_is_reraised(
    fail_at,
    commit_failure,
    expected_events,
):
    events: list[str] = []
    repository = FakeTicketRepository(
        events,
        build_context(),
        fail_at=fail_at,
    )
    transaction = FakeTransaction(
        events,
        failure=commit_failure,
    )
    service = TicketCreationService(repository, transaction)

    expected_message = (
        f"Synthetic {fail_at} failure"
        if fail_at is not None
        else "Synthetic commit failure"
    )

    with pytest.raises(
        RuntimeError,
        match=f"^{expected_message}$",
    ):
        service.create(
            actor_user_id=42,
            organization_id=100,
            title="Login problem",
            description="Login is unavailable.",
            priority="medium",
        )

    assert events == expected_events
