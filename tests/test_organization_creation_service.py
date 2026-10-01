import pytest

from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
    Organization,
    OrganizationMembership,
)
from opsdesk.organizations.repositories import OrganizationConcurrencyError
from opsdesk.organizations.services import (
    OrganizationActorUnavailableError,
    OrganizationCreationBusyError,
    OrganizationCreationService,
)


def build_user(*, is_active: bool = True) -> User:
    return User(
        user_id=42,
        email="actor@example.com",
        password_hash="synthetic_password_hash",
        is_active=is_active,
    )


class FakeOrganizationRepository:
    def __init__(
        self,
        events: list[str],
        actor: User | None,
        *,
        fail_at: str | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.events = events
        self.actor = actor
        self.fail_at = fail_at
        self.failure = failure
        self.received_organization = None
        self.received_membership = None

    def _raise_if_requested(self, step: str) -> None:
        if self.fail_at == step:
            if self.failure is None:
                raise RuntimeError(f"Synthetic {step} failure")
            raise self.failure

    def lock_user_for_organization_creation(
        self,
        user_id: int,
    ) -> User | None:
        self.events.append("lock_user")
        self._raise_if_requested("lock_user")

        if self.actor is not None:
            assert user_id == self.actor.user_id

        return self.actor

    def create_organization(
        self,
        new_organization: NewOrganization,
    ) -> Organization:
        self.events.append("create_organization")
        self.received_organization = new_organization
        self._raise_if_requested("create_organization")

        return Organization(
            organization_id=100,
            name=new_organization.name,
            is_active=True,
        )

    def create_membership(
        self,
        new_membership: NewOrganizationMembership,
    ) -> OrganizationMembership:
        self.events.append("create_membership")
        self.received_membership = new_membership
        self._raise_if_requested("create_membership")

        return OrganizationMembership(
            membership_id=200,
            user_id=new_membership.user_id,
            organization_id=new_membership.organization_id,
            role=new_membership.role,
            is_active=True,
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


def test_creation_locks_actor_creates_owner_and_commits():
    events: list[str] = []
    repository = FakeOrganizationRepository(events, build_user())
    transaction = FakeTransaction(events)
    service = OrganizationCreationService(repository, transaction)

    result = service.create(
        actor_user_id=42,
        name="Özdemir Yazılım",
    )

    assert repository.received_organization == NewOrganization(name="Özdemir Yazılım")
    assert repository.received_membership == NewOrganizationMembership(
        user_id=42,
        organization_id=100,
        role="owner",
    )
    assert result.organization.organization_id == 100
    assert result.own_membership.membership_id == 200
    assert result.own_membership.role == "owner"
    assert events == [
        "lock_user",
        "create_organization",
        "create_membership",
        "commit",
    ]


@pytest.mark.parametrize(
    "actor",
    [
        None,
        build_user(is_active=False),
    ],
)
def test_missing_or_inactive_actor_rolls_back_without_writes(actor):
    events: list[str] = []
    repository = FakeOrganizationRepository(events, actor)
    transaction = FakeTransaction(events)
    service = OrganizationCreationService(repository, transaction)

    with pytest.raises(OrganizationActorUnavailableError):
        service.create(
            actor_user_id=42,
            name="Acme",
        )

    assert repository.received_organization is None
    assert repository.received_membership is None
    assert events == [
        "lock_user",
        "rollback",
    ]


@pytest.mark.parametrize(
    ("fail_at", "expected_events"),
    [
        (
            "create_organization",
            [
                "lock_user",
                "create_organization",
                "rollback",
            ],
        ),
        (
            "create_membership",
            [
                "lock_user",
                "create_organization",
                "create_membership",
                "rollback",
            ],
        ),
    ],
)
def test_unknown_write_failure_rolls_back_and_is_reraised(
    fail_at,
    expected_events,
):
    events: list[str] = []
    repository = FakeOrganizationRepository(
        events,
        build_user(),
        fail_at=fail_at,
    )
    transaction = FakeTransaction(events)
    service = OrganizationCreationService(repository, transaction)

    with pytest.raises(
        RuntimeError,
        match=f"^Synthetic {fail_at} failure$",
    ):
        service.create(
            actor_user_id=42,
            name="Acme",
        )

    assert events == expected_events


def test_commit_failure_rolls_back_and_is_reraised():
    events: list[str] = []
    repository = FakeOrganizationRepository(events, build_user())
    transaction = FakeTransaction(
        events,
        failure=RuntimeError("Synthetic commit failure"),
    )
    service = OrganizationCreationService(repository, transaction)

    with pytest.raises(
        RuntimeError,
        match="^Synthetic commit failure$",
    ):
        service.create(
            actor_user_id=42,
            name="Acme",
        )

    assert events == [
        "lock_user",
        "create_organization",
        "create_membership",
        "commit",
        "rollback",
    ]


@pytest.mark.parametrize(
    ("fail_at", "commit_failure", "expected_events"),
    [
        (
            "lock_user",
            None,
            [
                "lock_user",
                "rollback",
            ],
        ),
        (
            "create_organization",
            None,
            [
                "lock_user",
                "create_organization",
                "rollback",
            ],
        ),
        (
            "create_membership",
            None,
            [
                "lock_user",
                "create_organization",
                "create_membership",
                "rollback",
            ],
        ),
        (
            None,
            OrganizationConcurrencyError(),
            [
                "lock_user",
                "create_organization",
                "create_membership",
                "commit",
                "rollback",
            ],
        ),
    ],
)
def test_recognized_concurrency_failure_becomes_busy_error(
    fail_at,
    commit_failure,
    expected_events,
):
    events: list[str] = []
    repository = FakeOrganizationRepository(
        events,
        build_user(),
        fail_at=fail_at,
        failure=(OrganizationConcurrencyError() if fail_at is not None else None),
    )
    transaction = FakeTransaction(
        events,
        failure=commit_failure,
    )
    service = OrganizationCreationService(repository, transaction)

    with pytest.raises(OrganizationCreationBusyError):
        service.create(
            actor_user_id=42,
            name="Acme",
        )

    assert events == expected_events
