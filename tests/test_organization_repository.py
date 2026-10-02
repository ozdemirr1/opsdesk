import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from opsdesk.db.models.organization import OrganizationRow
from opsdesk.db.models.organization_membership import (
    OrganizationMembershipRow,
)
from opsdesk.db.models.user import UserRow
from opsdesk.db.repositories.organizations import (
    LOCK_TIMEOUT_STATEMENT,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyOrganizationTransaction,
)
from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
)
from opsdesk.organizations.repositories import OrganizationConcurrencyError


class SyntheticDatabaseFailure(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__("Synthetic database failure")
        self.sqlstate = sqlstate


def build_database_error(sqlstate: str) -> OperationalError:
    return OperationalError(
        "synthetic statement",
        {},
        SyntheticDatabaseFailure(sqlstate),
    )


class FakeSession:
    def __init__(
        self,
        *,
        user_row: UserRow | None = None,
        failure_at: str | None = None,
        database_error: OperationalError | None = None,
    ) -> None:
        self.user_row = user_row
        self.failure_at = failure_at
        self.database_error = database_error
        self.events: list[str] = []
        self.execute_statement = None
        self.scalar_statement = None
        self.added_row = None

    def _raise_if_requested(self, step: str) -> None:
        if self.failure_at == step:
            if self.database_error is None:
                raise RuntimeError(f"Synthetic {step} failure")
            raise self.database_error

    def execute(self, statement):
        self.events.append("execute")
        self.execute_statement = statement
        self._raise_if_requested("execute")

    def scalar(self, statement):
        self.events.append("scalar")
        self.scalar_statement = statement
        self._raise_if_requested("scalar")
        return self.user_row

    def add(self, row) -> None:
        self.events.append("add")
        self.added_row = row

    def flush(self) -> None:
        self.events.append("flush")
        self._raise_if_requested("flush")

        if isinstance(self.added_row, OrganizationRow):
            self.added_row.organization_id = 100

        if isinstance(self.added_row, OrganizationMembershipRow):
            self.added_row.membership_id = 200

    def commit(self) -> None:
        self.events.append("commit")
        self._raise_if_requested("commit")

    def rollback(self) -> None:
        self.events.append("rollback")


def build_user_row(*, is_active: bool = True) -> UserRow:
    return UserRow(
        user_id=42,
        email="actor@example.com",
        password_hash="synthetic_password_hash",
        is_active=is_active,
    )


def test_user_lock_sets_local_timeout_and_uses_for_share():
    session = FakeSession(user_row=build_user_row())
    repository = SqlAlchemyOrganizationRepository(session)

    user = repository.lock_user_for_organization_creation(42)

    assert user is not None
    assert user.user_id == 42
    assert user.is_active is True
    assert session.events == [
        "execute",
        "scalar",
    ]
    assert session.execute_statement.text == LOCK_TIMEOUT_STATEMENT

    compiled_statement = str(
        session.scalar_statement.compile(
            dialect=postgresql.dialect(),
        )
    )

    assert "FOR SHARE" in compiled_statement
    assert "users.user_id =" in compiled_statement


def test_missing_user_is_returned_as_none_after_lock_query():
    session = FakeSession(user_row=None)
    repository = SqlAlchemyOrganizationRepository(session)

    user = repository.lock_user_for_organization_creation(999)

    assert user is None
    assert session.events == [
        "execute",
        "scalar",
    ]


def test_create_organization_flushes_and_returns_domain_model():
    session = FakeSession()
    repository = SqlAlchemyOrganizationRepository(session)

    organization = repository.create_organization(NewOrganization(name="Acme"))

    assert isinstance(session.added_row, OrganizationRow)
    assert session.added_row.name == "Acme"
    assert session.added_row.is_active is True
    assert organization.organization_id == 100
    assert organization.name == "Acme"
    assert organization.is_active is True
    assert session.events == [
        "add",
        "flush",
    ]


def test_create_membership_flushes_server_derived_owner():
    session = FakeSession()
    repository = SqlAlchemyOrganizationRepository(session)

    membership = repository.create_membership(
        NewOrganizationMembership(
            user_id=42,
            organization_id=100,
            role="owner",
        )
    )

    assert isinstance(
        session.added_row,
        OrganizationMembershipRow,
    )
    assert session.added_row.user_id == 42
    assert session.added_row.organization_id == 100
    assert session.added_row.role == "owner"
    assert session.added_row.is_active is True
    assert membership.membership_id == 200
    assert membership.user_id == 42
    assert membership.organization_id == 100
    assert membership.role == "owner"
    assert membership.is_active is True
    assert session.events == [
        "add",
        "flush",
    ]


@pytest.mark.parametrize(
    "sqlstate",
    [
        "55P03",
        "40P01",
        "40001",
    ],
)
@pytest.mark.parametrize(
    "failure_at",
    [
        "execute",
        "scalar",
    ],
)
def test_recognized_lock_failures_are_translated(
    sqlstate,
    failure_at,
):
    session = FakeSession(
        user_row=build_user_row(),
        failure_at=failure_at,
        database_error=build_database_error(sqlstate),
    )
    repository = SqlAlchemyOrganizationRepository(session)

    with pytest.raises(OrganizationConcurrencyError):
        repository.lock_user_for_organization_creation(42)


@pytest.mark.parametrize(
    "operation",
    [
        "organization",
        "membership",
    ],
)
def test_recognized_flush_failure_is_translated(operation):
    session = FakeSession(
        failure_at="flush",
        database_error=build_database_error("40P01"),
    )
    repository = SqlAlchemyOrganizationRepository(session)

    with pytest.raises(OrganizationConcurrencyError):
        if operation == "organization":
            repository.create_organization(NewOrganization(name="Acme"))
        else:
            repository.create_membership(
                NewOrganizationMembership(
                    user_id=42,
                    organization_id=100,
                    role="owner",
                )
            )


def test_unknown_database_failure_is_not_hidden():
    database_error = build_database_error("08006")
    session = FakeSession(
        user_row=build_user_row(),
        failure_at="scalar",
        database_error=database_error,
    )
    repository = SqlAlchemyOrganizationRepository(session)

    with pytest.raises(OperationalError) as captured:
        repository.lock_user_for_organization_creation(42)

    assert captured.value is database_error


@pytest.mark.parametrize(
    "sqlstate",
    [
        "55P03",
        "40P01",
        "40001",
    ],
)
def test_recognized_commit_failure_is_translated(sqlstate):
    session = FakeSession(
        failure_at="commit",
        database_error=build_database_error(sqlstate),
    )
    transaction = SqlAlchemyOrganizationTransaction(session)

    with pytest.raises(OrganizationConcurrencyError):
        transaction.commit()

    assert session.events == ["commit"]


def test_unknown_commit_failure_is_not_hidden():
    database_error = build_database_error("08006")
    session = FakeSession(
        failure_at="commit",
        database_error=database_error,
    )
    transaction = SqlAlchemyOrganizationTransaction(session)

    with pytest.raises(OperationalError) as captured:
        transaction.commit()

    assert captured.value is database_error


def test_transaction_rollback_delegates_to_session():
    session = FakeSession()
    transaction = SqlAlchemyOrganizationTransaction(session)

    transaction.rollback()

    assert session.events == ["rollback"]
