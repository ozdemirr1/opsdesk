from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.identity.token_config import TokenSettings
from opsdesk.main import create_app

SECRET = "a" * 64
FIXED_NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def build_user() -> User:
    return User(
        user_id=42,
        email="current@example.com",
        password_hash="secret-hash-that-must-not-be-returned",
        is_active=True,
    )


def test_current_user_endpoint_returns_only_public_profile():
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_current_user] = build_user

    with TestClient(app) as client:
        response = client.get("/users/me")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": 42,
        "email": "current@example.com",
        "is_active": True,
    }
    assert "password" not in response.text
    assert "secret-hash" not in response.text


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Basic synthetic-credentials",
    ],
)
def test_missing_or_wrong_authentication_scheme_returns_bearer_401(
    authorization,
):
    app = create_app(Settings(environment="test"))
    headers = {}

    if authorization is not None:
        headers["Authorization"] = authorization

    with TestClient(app) as client:
        response = client.get(
            "/users/me",
            headers=headers,
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


def test_invalid_bearer_token_is_rejected_before_database_lookup():
    session_factory = Mock()
    app = create_app(
        Settings(environment="test"),
        session_factory=session_factory,
        token_settings=TokenSettings(secret=SECRET),
        token_clock=lambda: FIXED_NOW,
    )

    with TestClient(app) as client:
        response = client.get(
            "/users/me",
            headers={
                "Authorization": "Bearer malformed-token-marker",
            },
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"
    assert "malformed-token-marker" not in response.text
    session_factory.assert_not_called()
