from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from opsdesk.config import Settings
from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    UserRow,
)
from opsdesk.db.session import session_scope
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer
from opsdesk.main import create_app

SECRET = "a" * 64
OTHER_SECRET = "b" * 64
FIXED_NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)

UNAUTHENTICATED_RESPONSE = {
    "error": {
        "code": "unauthenticated",
        "message": "Authentication required.",
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


def issue_token(
    user_id: int,
    *,
    secret: str = SECRET,
    issued_at: datetime = FIXED_NOW,
) -> str:
    issuer = AccessTokenIssuer(
        TokenSettings(secret=secret),
        clock=lambda: issued_at,
    )
    return issuer.issue(user_id)


def bearer_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


def assert_unauthenticated(response) -> None:
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == UNAUTHENTICATED_RESPONSE
    assert SECRET not in response.text


def assert_identity_counts(
    factory,
    *,
    users: int,
    organizations: int = 0,
    memberships: int = 0,
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
def test_register_login_and_current_user_complete_identity_flow(
    identity_scope,
):
    email = "identity-flow@example.com"
    password = "correct horse battery staple"

    with identity_scope() as factory:
        app = build_app(factory)

        with TestClient(app) as client:
            registration_response = client.post(
                "/users",
                json={
                    "email": email,
                    "password": password,
                },
            )
            login_response = client.post(
                "/auth/login",
                json={
                    "email": email,
                    "password": password,
                },
            )

            access_token = login_response.json()["access_token"]

            current_user_response = client.get(
                "/users/me",
                headers=bearer_headers(access_token),
            )

        assert registration_response.status_code == 201
        assert login_response.status_code == 200
        assert current_user_response.status_code == 200
        assert current_user_response.json() == registration_response.json()
        assert current_user_response.json() == {
            "user_id": registration_response.json()["user_id"],
            "email": email,
            "is_active": True,
        }
        assert password not in current_user_response.text
        assert "password_hash" not in current_user_response.text

        with session_scope(factory) as session:
            stored_user = session.scalar(select(UserRow).where(UserRow.email == email))

            assert stored_user is not None
            assert stored_user.password_hash != password

        assert_identity_counts(factory, users=1)


@pytest.mark.integration
def test_current_user_accepts_controlled_signed_token(
    identity_scope,
):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            user = UserRow(
                email="controlled-token@example.com",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
            session.add(user)
            session.commit()
            user_id = user.user_id

        token = issue_token(user_id)
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/users/me",
                headers=bearer_headers(token),
            )

        assert response.status_code == 200
        assert response.json() == {
            "user_id": user_id,
            "email": "controlled-token@example.com",
            "is_active": True,
        }
        assert "synthetic-password-hash" not in response.text

        assert_identity_counts(factory, users=1)


@pytest.mark.integration
def test_same_token_is_rejected_after_user_is_deactivated(
    identity_scope,
):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            user = UserRow(
                email="deactivated@example.com",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
            session.add(user)
            session.commit()
            user_id = user.user_id

        token = issue_token(user_id)
        app = build_app(factory)

        with TestClient(app) as client:
            active_response = client.get(
                "/users/me",
                headers=bearer_headers(token),
            )

            with session_scope(factory) as session:
                stored_user = session.get(UserRow, user_id)

                assert stored_user is not None
                stored_user.is_active = False
                session.commit()

            inactive_response = client.get(
                "/users/me",
                headers=bearer_headers(token),
            )

        assert active_response.status_code == 200
        assert_unauthenticated(inactive_response)
        assert_identity_counts(factory, users=1)


@pytest.mark.integration
def test_token_for_missing_user_is_rejected_without_creating_data(
    identity_scope,
):
    with identity_scope() as factory:
        token = issue_token(9_999_999)
        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/users/me",
                headers=bearer_headers(token),
            )

        assert_unauthenticated(response)
        assert_identity_counts(factory, users=0)


@pytest.mark.integration
@pytest.mark.parametrize(
    "failure_case",
    [
        "malformed",
        "wrong-signature",
        "expired",
    ],
)
def test_invalid_tokens_share_safe_unauthenticated_response(
    identity_scope,
    failure_case,
):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            user = UserRow(
                email="invalid-token@example.com",
                password_hash="synthetic-password-hash",
                is_active=True,
            )
            session.add(user)
            session.commit()
            user_id = user.user_id

        if failure_case == "malformed":
            token = "malformed-token-marker"
        elif failure_case == "wrong-signature":
            token = issue_token(
                user_id,
                secret=OTHER_SECRET,
            )
        else:
            token = issue_token(
                user_id,
                issued_at=FIXED_NOW - timedelta(seconds=1800),
            )

        app = build_app(factory)

        with TestClient(app) as client:
            response = client.get(
                "/users/me",
                headers=bearer_headers(token),
            )

        assert_unauthenticated(response)
        assert "malformed-token-marker" not in response.text
        assert OTHER_SECRET not in response.text
        assert_identity_counts(factory, users=1)
