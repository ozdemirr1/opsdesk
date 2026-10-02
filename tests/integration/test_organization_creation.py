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
    UserRow,
)
from opsdesk.db.repositories.organizations import (
    SqlAlchemyOrganizationRepository,
    SqlAlchemyOrganizationTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer
from opsdesk.main import create_app
from opsdesk.organizations.dependencies import (
    get_organization_creation_service,
)
from opsdesk.organizations.services import OrganizationCreationService

SECRET = "a" * 64
FIXED_NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def build_app(factory):
    return create_app(
        Settings(environment="test"),
        session_factory=factory,
        token_settings=TokenSettings(secret=SECRET),
        token_clock=lambda: FIXED_NOW,
    )


def issue_token(user_id: int) -> str:
    issuer = AccessTokenIssuer(
        TokenSettings(secret=SECRET),
        clock=lambda: FIXED_NOW,
    )
    return issuer.issue(user_id)


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


def assert_counts(
    factory,
    *,
    users: int,
    organizations: int,
    memberships: int,
) -> None:
    with session_scope(factory) as session:
        assert session.scalar(select(func.count()).select_from(UserRow)) == users
        assert (
            session.scalar(select(func.count()).select_from(OrganizationRow))
            == organizations
        )
        assert (
            session.scalar(select(func.count()).select_from(OrganizationMembershipRow))
            == memberships
        )


@pytest.mark.integration
def test_http_creation_persists_organization_and_owner(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="organization-owner@example.com",
        )
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                "/organizations",
                json={
                    "name": "  Özdemir Yazılım  ",
                },
                headers=bearer_headers(user_id),
            )

        assert response.status_code == 201

        payload = response.json()
        organization_id = payload["organization"]["organization_id"]
        membership_id = payload["own_membership"]["membership_id"]

        assert payload == {
            "organization": {
                "organization_id": organization_id,
                "name": "Özdemir Yazılım",
                "is_active": True,
            },
            "own_membership": {
                "membership_id": membership_id,
                "organization_id": organization_id,
                "role": "owner",
                "is_active": True,
            },
        }
        assert "user_id" not in response.text
        assert "password" not in response.text

        with session_scope(factory) as verification_session:
            stored_organization = verification_session.get(
                OrganizationRow,
                organization_id,
            )
            stored_membership = verification_session.get(
                OrganizationMembershipRow,
                membership_id,
            )

            assert stored_organization is not None
            assert stored_organization.name == "Özdemir Yazılım"
            assert stored_organization.is_active is True

            assert stored_membership is not None
            assert stored_membership.user_id == user_id
            assert stored_membership.organization_id == organization_id
            assert stored_membership.role == "owner"
            assert stored_membership.is_active is True

        assert_counts(
            factory,
            users=1,
            organizations=1,
            memberships=1,
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "existing_role",
    [
        "owner",
        "admin",
        "agent",
        "customer",
    ],
)
def test_role_in_another_organization_does_not_control_creation(
    identity_scope,
    existing_role,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email=f"existing-{existing_role}@example.com",
        )

        with session_scope(factory) as setup_session:
            existing_organization = OrganizationRow(
                name=f"Existing {existing_role}",
                is_active=True,
            )
            setup_session.add(existing_organization)
            setup_session.flush()

            existing_membership = OrganizationMembershipRow(
                user_id=user_id,
                organization_id=(existing_organization.organization_id),
                role=existing_role,
                is_active=True,
            )
            setup_session.add(existing_membership)
            setup_session.commit()

            existing_organization_id = existing_organization.organization_id
            existing_membership_id = existing_membership.membership_id

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                "/organizations",
                json={
                    "name": "New Independent Organization",
                },
                headers=bearer_headers(user_id),
            )

        assert response.status_code == 201

        payload = response.json()
        new_organization_id = payload["organization"]["organization_id"]
        new_membership_id = payload["own_membership"]["membership_id"]

        assert new_organization_id != existing_organization_id
        assert payload["own_membership"]["role"] == "owner"

        with session_scope(factory) as verification_session:
            original_membership = verification_session.get(
                OrganizationMembershipRow,
                existing_membership_id,
            )
            new_membership = verification_session.get(
                OrganizationMembershipRow,
                new_membership_id,
            )

            assert original_membership is not None
            assert original_membership.role == existing_role
            assert original_membership.is_active is True

            assert new_membership is not None
            assert new_membership.user_id == user_id
            assert new_membership.organization_id == new_organization_id
            assert new_membership.role == "owner"
            assert new_membership.is_active is True

        assert_counts(
            factory,
            users=1,
            organizations=2,
            memberships=2,
        )


@pytest.mark.integration
def test_duplicate_display_names_create_distinct_organizations(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="duplicate-name-owner@example.com",
        )
        app = build_app(factory)

        with TestClient(app) as client:
            first_response = client.post(
                "/organizations",
                json={
                    "name": "Shared Display Name",
                },
                headers=bearer_headers(user_id),
            )
            second_response = client.post(
                "/organizations",
                json={
                    "name": "Shared Display Name",
                },
                headers=bearer_headers(user_id),
            )

        assert first_response.status_code == 201
        assert second_response.status_code == 201

        first_payload = first_response.json()
        second_payload = second_response.json()

        first_organization_id = first_payload["organization"]["organization_id"]
        second_organization_id = second_payload["organization"]["organization_id"]

        assert first_organization_id != second_organization_id
        assert (
            first_payload["organization"]["name"]
            == second_payload["organization"]["name"]
            == "Shared Display Name"
        )

        with session_scope(factory) as verification_session:
            organizations = verification_session.scalars(
                select(OrganizationRow).order_by(OrganizationRow.organization_id)
            ).all()
            memberships = verification_session.scalars(
                select(OrganizationMembershipRow).order_by(
                    OrganizationMembershipRow.membership_id
                )
            ).all()

            assert len(organizations) == 2
            assert {organization.name for organization in organizations} == {
                "Shared Display Name"
            }

            assert len(memberships) == 2
            assert {membership.organization_id for membership in memberships} == {
                first_organization_id,
                second_organization_id,
            }
            assert all(
                membership.user_id == user_id
                and membership.role == "owner"
                and membership.is_active
                for membership in memberships
            )


@pytest.mark.integration
def test_inactive_user_cannot_create_persistent_records(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="inactive-creator@example.com",
            is_active=False,
        )
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.post(
                "/organizations",
                json={
                    "name": "Must Not Persist",
                },
                headers=bearer_headers(user_id),
            )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json() == {
            "error": {
                "code": "unauthenticated",
                "message": "Authentication required.",
                "details": [],
            }
        }

        assert_counts(
            factory,
            users=1,
            organizations=0,
            memberships=0,
        )


class FailingMembershipRepository:
    def __init__(self, repository) -> None:
        self._repository = repository

    def lock_user_for_organization_creation(
        self,
        user_id: int,
    ):
        return self._repository.lock_user_for_organization_creation(user_id)

    def create_organization(self, new_organization):
        return self._repository.create_organization(new_organization)

    def create_membership(self, new_membership):
        raise RuntimeError("Synthetic membership write failure")


class FailingCommitTransaction:
    def __init__(self, session) -> None:
        self._session = session
        self.commit_called = False
        self.rollback_called = False

    def commit(self) -> None:
        self.commit_called = True
        raise RuntimeError("Synthetic commit boundary failure")

    def rollback(self) -> None:
        self.rollback_called = True
        self._session.rollback()


@pytest.mark.integration
def test_membership_failure_rolls_back_new_organization_only(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="membership-failure@example.com",
        )

        with session_scope(factory) as setup_session:
            existing_organization = OrganizationRow(
                name="Existing Organization",
                is_active=True,
            )
            setup_session.add(existing_organization)
            setup_session.flush()

            existing_membership = OrganizationMembershipRow(
                user_id=user_id,
                organization_id=(existing_organization.organization_id),
                role="customer",
                is_active=True,
            )
            setup_session.add(existing_membership)
            setup_session.commit()

            existing_organization_id = existing_organization.organization_id
            existing_membership_id = existing_membership.membership_id

        with session_scope(factory) as creation_session:
            repository = FailingMembershipRepository(
                SqlAlchemyOrganizationRepository(creation_session)
            )
            service = OrganizationCreationService(
                repository=repository,
                transaction=SqlAlchemyOrganizationTransaction(creation_session),
            )

            with pytest.raises(
                RuntimeError,
                match=("^Synthetic membership write failure$"),
            ):
                service.create(
                    actor_user_id=user_id,
                    name="Must Roll Back",
                )

        with session_scope(factory) as verification_session:
            organizations = verification_session.scalars(
                select(OrganizationRow).order_by(OrganizationRow.organization_id)
            ).all()
            memberships = verification_session.scalars(
                select(OrganizationMembershipRow).order_by(
                    OrganizationMembershipRow.membership_id
                )
            ).all()

            assert len(organizations) == 1
            assert organizations[0].organization_id == existing_organization_id
            assert organizations[0].name == ("Existing Organization")
            assert organizations[0].is_active is True

            assert len(memberships) == 1
            assert memberships[0].membership_id == existing_membership_id
            assert memberships[0].user_id == user_id
            assert memberships[0].role == "customer"
            assert memberships[0].is_active is True


@pytest.mark.integration
def test_commit_boundary_failure_rolls_back_flushed_records(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="commit-failure@example.com",
        )

        with session_scope(factory) as creation_session:
            transaction = FailingCommitTransaction(creation_session)
            service = OrganizationCreationService(
                repository=SqlAlchemyOrganizationRepository(creation_session),
                transaction=transaction,
            )

            with pytest.raises(
                RuntimeError,
                match=("^Synthetic commit boundary failure$"),
            ):
                service.create(
                    actor_user_id=user_id,
                    name="Must Also Roll Back",
                )

            assert transaction.commit_called is True
            assert transaction.rollback_called is True

        assert_counts(
            factory,
            users=1,
            organizations=0,
            memberships=0,
        )


@pytest.mark.integration
def test_unknown_constraint_failure_is_not_mapped_to_busy(
    identity_scope,
):
    with identity_scope() as factory:
        user_id = create_user(
            factory,
            email="constraint-failure@example.com",
        )

        with session_scope(factory) as creation_session:
            service = OrganizationCreationService(
                repository=SqlAlchemyOrganizationRepository(creation_session),
                transaction=SqlAlchemyOrganizationTransaction(creation_session),
            )

            with pytest.raises(IntegrityError) as exc_info:
                service.create(
                    actor_user_id=user_id,
                    name="",
                )

        assert (
            exc_info.value.orig.diag.constraint_name == "ck_organizations_name_length"
        )

        assert_counts(
            factory,
            users=1,
            organizations=0,
            memberships=0,
        )


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
        "The Organization request was not observed "
        "waiting on the expected database lock."
    )


@pytest.mark.integration
def test_user_lock_timeout_is_503_while_other_user_progresses(
    identity_scope,
):
    worker_pids: Queue[int] = Queue()

    with identity_scope() as factory:
        blocked_user_id = create_user(
            factory,
            email="blocked-creator@example.com",
        )
        independent_user_id = create_user(
            factory,
            email="independent-creator@example.com",
        )

        def get_observed_creation_service():
            with session_scope(factory) as session:
                worker_pid = session.scalar(text("SELECT pg_backend_pid()"))
                worker_pids.put(worker_pid)

                repository = SqlAlchemyOrganizationRepository(session)

                yield OrganizationCreationService(
                    repository=repository,
                    transaction=(SqlAlchemyOrganizationTransaction(session)),
                )

        app = build_app(factory)
        app.dependency_overrides[get_organization_creation_service] = (
            get_observed_creation_service
        )

        with TestClient(app) as client:
            with session_scope(factory) as blocker_session:
                blocker_pid = blocker_session.scalar(text("SELECT pg_backend_pid()"))

                locked_user = blocker_session.scalar(
                    select(UserRow)
                    .where(UserRow.user_id == blocked_user_id)
                    .with_for_update()
                )

                assert locked_user is not None

                with ThreadPoolExecutor(max_workers=1) as executor:
                    blocked_future = executor.submit(
                        client.post,
                        "/organizations",
                        json={
                            "name": ("Blocked Organization"),
                        },
                        headers=bearer_headers(blocked_user_id),
                    )

                    worker_pid = worker_pids.get(timeout=5)

                    observed_blockers = wait_for_database_blocker(
                        factory,
                        worker_pid=worker_pid,
                        expected_blocker_pid=(blocker_pid),
                    )

                    assert blocker_pid in observed_blockers

                    independent_response = client.post(
                        "/organizations",
                        json={
                            "name": ("Independent Organization"),
                        },
                        headers=bearer_headers(independent_user_id),
                    )

                    blocked_response = blocked_future.result(timeout=10)

                blocker_session.rollback()

        assert independent_response.status_code == 201
        assert (
            independent_response.json()["organization"]["name"]
            == "Independent Organization"
        )
        assert independent_response.json()["own_membership"]["role"] == "owner"

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
            organizations = verification_session.scalars(select(OrganizationRow)).all()
            memberships = verification_session.scalars(
                select(OrganizationMembershipRow)
            ).all()

            assert len(organizations) == 1
            assert organizations[0].name == "Independent Organization"

            assert len(memberships) == 1
            assert memberships[0].user_id == independent_user_id
            assert memberships[0].role == "owner"
            assert memberships[0].is_active is True

        assert_counts(
            factory,
            users=2,
            organizations=1,
            memberships=1,
        )
