from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_login_service
from opsdesk.identity.services import InvalidCredentialsError
from opsdesk.main import create_app

TOKEN = "synthetic-signed-access-token"
SECRET = "synthetic-login-secret-marker"


class RecordingLoginService:
    def __init__(
        self,
        *,
        token: str = TOKEN,
        error: Exception | None = None,
    ) -> None:
        self.token = token
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def login(
        self,
        *,
        email: str,
        plain_password: str,
    ) -> str:
        self.calls.append((email, plain_password))

        if self.error is not None:
            raise self.error

        return self.token


def build_client(service: RecordingLoginService) -> TestClient:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_login_service] = lambda: service
    return TestClient(app)


def test_login_returns_bearer_token_after_normalization():
    service = RecordingLoginService()
    decomposed_password = "e\u0301" + "a" * 14

    with build_client(service) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": "  USER@EXAMPLE.COM  ",
                "password": decomposed_password,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": TOKEN,
        "token_type": "bearer",
    }
    assert service.calls == [
        ("user@example.com", "\u00e9" + "a" * 14),
    ]
    assert UUID(response.headers["x-request-id"]).version == 4


@pytest.mark.parametrize(
    "failure_case",
    [
        "unknown-email",
        "wrong-password",
        "inactive-user",
    ],
)
def test_credential_failures_share_one_public_response(failure_case):
    service = RecordingLoginService(
        error=InvalidCredentialsError(),
    )

    with build_client(service) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": f"{failure_case}@example.com",
                "password": "river valley lantern",
            },
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
    assert "access_token" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "missing-password@example.com"},
        {"password": "river valley lantern"},
        {
            "email": 123,
            "password": "river valley lantern",
        },
        {
            "email": "extra@example.com",
            "password": "river valley lantern",
            "role": "owner",
        },
        {
            "email": "short@example.com",
            "password": "too-short",
        },
    ],
)
def test_invalid_login_never_calls_service(payload):
    service = RecordingLoginService()

    with build_client(service) as client:
        response = client.post(
            "/auth/login",
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert service.calls == []
    assert "access_token" not in response.text


def test_unexpected_login_failure_is_safe():
    service = RecordingLoginService(
        error=RuntimeError(SECRET),
    )

    with build_client(service) as client:
        response = client.post(
            "/auth/login",
            json={
                "email": "failure@example.com",
                "password": "river valley lantern",
            },
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert SECRET not in response.text
    assert "access_token" not in response.text
