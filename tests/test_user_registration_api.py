from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_registration_service
from opsdesk.identity.models import User
from opsdesk.identity.services import EmailAlreadyExistsError
from opsdesk.main import create_app

SECRET = "synthetic-private-password-marker"


class RecordingRegistrationService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def register_user(
        self,
        *,
        email: str,
        plain_password: str,
    ) -> User:
        self.calls.append((email, plain_password))

        if self.error is not None:
            raise self.error

        return User(
            user_id=42,
            email=email,
            password_hash=f"hidden-{SECRET}",
            is_active=True,
        )


def build_client(service: RecordingRegistrationService) -> TestClient:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_registration_service] = lambda: service
    return TestClient(app)


def test_registration_returns_committed_public_user_projection():
    service = RecordingRegistrationService()
    decomposed_password = "e\u0301" + "a" * 14

    with build_client(service) as client:
        response = client.post(
            "/users",
            json={
                "email": "  USER@EXAMPLE.COM  ",
                "password": decomposed_password,
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": 42,
        "email": "user@example.com",
        "is_active": True,
    }
    assert service.calls == [
        ("user@example.com", "\u00e9" + "a" * 14),
    ]
    assert SECRET not in response.text
    assert UUID(response.headers["x-request-id"]).version == 4


def test_duplicate_registration_uses_public_conflict():
    service = RecordingRegistrationService(
        error=EmailAlreadyExistsError(),
    )

    with build_client(service) as client:
        response = client.post(
            "/users",
            json={
                "email": "duplicate@example.com",
                "password": "river valley lantern",
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "email_already_exists",
            "message": "Email already exists.",
            "details": [],
        }
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "missing-password@example.com"},
        {"email": 123, "password": "river valley lantern"},
        {
            "email": "extra@example.com",
            "password": "river valley lantern",
            "role": "owner",
        },
        {"email": "short@example.com", "password": "too-short"},
    ],
)
def test_invalid_registration_never_calls_service(payload):
    service = RecordingRegistrationService()

    with build_client(service) as client:
        response = client.post("/users", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert service.calls == []
    assert SECRET not in response.text


def test_unexpected_registration_failure_is_safe():
    service = RecordingRegistrationService(
        error=RuntimeError(SECRET),
    )

    with build_client(service) as client:
        response = client.post(
            "/users",
            json={
                "email": "failure@example.com",
                "password": "river valley lantern",
            },
        )

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert SECRET not in response.text
