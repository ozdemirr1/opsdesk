import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from opsdesk.config import Settings
from opsdesk.db.models import OrganizationMembershipRow, OrganizationRow, UserRow
from opsdesk.db.repositories.users import SqlAlchemyUserRepository
from opsdesk.db.session import session_scope
from opsdesk.identity.models import NewUser
from opsdesk.identity.passwords import PasswordHasher
from opsdesk.identity.repositories import UserEmailConflictError
from opsdesk.identity.services import EmailAlreadyExistsError, RegistrationService
from opsdesk.main import create_app


def build_registration_service(session):
    return RegistrationService(
        repository=SqlAlchemyUserRepository(session),
        transaction=session,
        password_hasher=PasswordHasher(),
    )


@pytest.mark.integration
def test_registration_commits_hash_and_public_user_state(identity_scope):
    plain_password = "river valley lantern"
    email = "registered@example.com"

    with identity_scope() as factory:
        with session_scope(factory) as session:
            service = build_registration_service(session)
            registered_user = service.register_user(
                email=email,
                plain_password=plain_password,
            )

        with session_scope(factory) as verification_session:
            stored_user = verification_session.get(
                UserRow,
                registered_user.user_id,
            )

            assert stored_user is not None
            assert stored_user.email == email
            assert stored_user.is_active is True
            assert stored_user.password_hash != plain_password
            assert PasswordHasher().verify_password(
                plain_password,
                stored_user.password_hash,
            )

            organization_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationRow)
            )
            membership_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationMembershipRow)
            )

            assert organization_count == 0
            assert membership_count == 0


@pytest.mark.integration
@pytest.mark.parametrize("existing_is_active", [True, False])
def test_registration_maps_only_duplicate_email_and_preserves_existing_user(
    identity_scope,
    existing_is_active,
):
    email = "duplicate-registration@example.com"

    with identity_scope() as factory:
        with session_scope(factory) as setup_session:
            existing_user = UserRow(
                email=email,
                password_hash="existing-test-hash",
                is_active=existing_is_active,
            )
            setup_session.add(existing_user)
            setup_session.commit()
            existing_user_id = existing_user.user_id

        with session_scope(factory) as registration_session:
            service = build_registration_service(registration_session)

            with pytest.raises(EmailAlreadyExistsError):
                service.register_user(
                    email=email,
                    plain_password="different safe password",
                )

        with session_scope(factory) as verification_session:
            users = verification_session.scalars(
                select(UserRow).order_by(UserRow.user_id)
            ).all()

            assert len(users) == 1
            assert users[0].user_id == existing_user_id
            assert users[0].email == email
            assert users[0].password_hash == "existing-test-hash"
            assert users[0].is_active is existing_is_active


@pytest.mark.integration
def test_repository_does_not_hide_unrelated_constraint_failure(identity_scope):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            repository = SqlAlchemyUserRepository(session)

            with pytest.raises(IntegrityError) as exc_info:
                repository.create(
                    NewUser(
                        email="Uppercase@example.com",
                        password_hash="test-only-hash",
                    )
                )

            session.rollback()

        assert exc_info.value.orig.diag.constraint_name == "ck_users_email_lowercase"

        with session_scope(factory) as verification_session:
            user_count = verification_session.scalar(
                select(func.count()).select_from(UserRow)
            )
            assert user_count == 0


@pytest.mark.integration
def test_repository_translates_only_named_email_unique_constraint(
    identity_scope,
):
    email = "repository-conflict@example.com"

    with identity_scope() as factory:
        with session_scope(factory) as setup_session:
            setup_session.add(
                UserRow(
                    email=email,
                    password_hash="existing-test-hash",
                )
            )
            setup_session.commit()

        with session_scope(factory) as session:
            repository = SqlAlchemyUserRepository(session)

            with pytest.raises(UserEmailConflictError):
                repository.create(
                    NewUser(
                        email=email,
                        password_hash="new-test-hash",
                    )
                )

            session.rollback()


@pytest.mark.integration
def test_http_registration_round_trip_and_duplicate_conflict(identity_scope):
    plain_password = "river valley lantern"

    with identity_scope() as factory:
        app = create_app(
            Settings(environment="test"),
            session_factory=factory,
        )

        with TestClient(app) as client:
            created_response = client.post(
                "/users",
                json={
                    "email": "  HTTP@EXAMPLE.COM  ",
                    "password": plain_password,
                },
            )
            duplicate_response = client.post(
                "/users",
                json={
                    "email": "http@example.com",
                    "password": "different safe password",
                },
            )

        assert created_response.status_code == 201
        assert created_response.json() == {
            "user_id": created_response.json()["user_id"],
            "email": "http@example.com",
            "is_active": True,
        }
        assert set(created_response.json()) == {
            "user_id",
            "email",
            "is_active",
        }

        assert duplicate_response.status_code == 409
        assert duplicate_response.json()["error"]["code"] == ("email_already_exists")

        with session_scope(factory) as verification_session:
            users = verification_session.scalars(
                select(UserRow).order_by(UserRow.user_id)
            ).all()

            assert len(users) == 1
            assert users[0].email == "http@example.com"
            assert users[0].password_hash != plain_password
            assert PasswordHasher().verify_password(
                plain_password,
                users[0].password_hash,
            )
