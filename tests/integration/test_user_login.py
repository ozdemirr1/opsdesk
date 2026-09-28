from datetime import UTC, datetime

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from opsdesk.config import Settings
from opsdesk.db.models import OrganizationMembershipRow, OrganizationRow, UserRow
from opsdesk.db.session import session_scope
from opsdesk.identity.passwords import PasswordHasher
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import (
    ACCESS_TOKEN_TTL_SECONDS,
    ALGORITHM,
    AUDIENCE,
    ISSUER,
)
from opsdesk.main import create_app

JWT_SECRET = "integration-test-jwt-secret-with-at-least-32-bytes"
FIXED_NOW = datetime(2026, 9, 28, 9, 30, tzinfo=UTC)


def build_login_app(factory):
    return create_app(
        Settings(environment="test"),
        session_factory=factory,
        token_settings=TokenSettings(secret=JWT_SECRET),
        token_clock=lambda: FIXED_NOW,
    )


@pytest.mark.integration
def test_http_login_reads_real_user_and_issues_verified_token(
    identity_scope,
):
    email = "login@example.com"
    plain_password = "river valley lantern"

    with identity_scope() as factory:
        with session_scope(factory) as setup_session:
            user = UserRow(
                email=email,
                password_hash=PasswordHasher().hash_password(
                    plain_password,
                ),
                is_active=True,
            )
            setup_session.add(user)
            setup_session.commit()
            user_id = user.user_id

        app = build_login_app(factory)

        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": "  LOGIN@EXAMPLE.COM  ",
                    "password": plain_password,
                },
            )

        assert response.status_code == 200
        assert set(response.json()) == {
            "access_token",
            "token_type",
        }
        assert response.json()["token_type"] == "bearer"

        access_token = response.json()["access_token"]
        header = jwt.get_unverified_header(access_token)
        claims = jwt.decode(
            access_token,
            JWT_SECRET,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={
                "verify_exp": False,
                "verify_iat": False,
            },
        )

        issued_at = int(FIXED_NOW.timestamp())

        assert header["alg"] == ALGORITHM
        assert claims == {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": issued_at + ACCESS_TOKEN_TTL_SECONDS,
            "iss": ISSUER,
            "aud": AUDIENCE,
        }

        with session_scope(factory) as verification_session:
            users = verification_session.scalars(
                select(UserRow).order_by(UserRow.user_id)
            ).all()
            organization_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationRow)
            )
            membership_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationMembershipRow)
            )

            assert len(users) == 1
            assert users[0].user_id == user_id
            assert users[0].email == email
            assert organization_count == 0
            assert membership_count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("failure_case", "submitted_email", "submitted_password"),
    [
        (
            "unknown-email",
            "unknown@example.com",
            "river valley lantern",
        ),
        (
            "wrong-password",
            "active@example.com",
            "incorrect password value",
        ),
        (
            "inactive-user",
            "inactive@example.com",
            "inactive user password",
        ),
    ],
)
def test_http_login_credential_failures_share_safe_response(
    identity_scope,
    failure_case,
    submitted_email,
    submitted_password,
):
    active_password = "active user password"
    inactive_password = "inactive user password"
    password_hasher = PasswordHasher()

    with identity_scope() as factory:
        with session_scope(factory) as setup_session:
            setup_session.add_all(
                [
                    UserRow(
                        email="active@example.com",
                        password_hash=password_hasher.hash_password(
                            active_password,
                        ),
                        is_active=True,
                    ),
                    UserRow(
                        email="inactive@example.com",
                        password_hash=password_hasher.hash_password(
                            inactive_password,
                        ),
                        is_active=False,
                    ),
                ]
            )
            setup_session.commit()

        app = build_login_app(factory)

        with TestClient(app) as client:
            response = client.post(
                "/auth/login",
                json={
                    "email": submitted_email,
                    "password": submitted_password,
                },
            )

        assert failure_case in {
            "unknown-email",
            "wrong-password",
            "inactive-user",
        }
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json() == {
            "error": {
                "code": "unauthenticated",
                "message": "Authentication required.",
                "details": [],
            }
        }
        assert "access_token" not in response.text
        assert JWT_SECRET not in response.text

        with session_scope(factory) as verification_session:
            user_count = verification_session.scalar(
                select(func.count()).select_from(UserRow)
            )
            organization_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationRow)
            )
            membership_count = verification_session.scalar(
                select(func.count()).select_from(OrganizationMembershipRow)
            )

            assert user_count == 2
            assert organization_count == 0
            assert membership_count == 0
