from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.main import create_app
from opsdesk.organizations.dependencies import (
    get_organization_creation_service,
)
from opsdesk.organizations.models import (
    Organization,
    OrganizationCreation,
    OrganizationMembership,
)
from opsdesk.organizations.services import (
    OrganizationActorUnavailableError,
    OrganizationCreationBusyError,
)

SECRET = "synthetic-private-database-marker"


def build_current_user() -> User:
    return User(
        user_id=42,
        email="actor@example.com",
        password_hash="private-password-hash",
        is_active=True,
    )


class RecordingOrganizationCreationService:
    def __init__(
        self,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.calls: list[tuple[int, str]] = []

    def create(
        self,
        *,
        actor_user_id: int,
        name: str,
    ) -> OrganizationCreation:
        self.calls.append((actor_user_id, name))

        if self.error is not None:
            raise self.error

        return OrganizationCreation(
            organization=Organization(
                organization_id=100,
                name=name,
                is_active=True,
            ),
            own_membership=OrganizationMembership(
                membership_id=200,
                user_id=actor_user_id,
                organization_id=100,
                role="owner",
                is_active=True,
            ),
        )


def build_client(
    service: RecordingOrganizationCreationService,
    *,
    authenticated: bool = True,
) -> TestClient:
    app = create_app(Settings(environment="test"))

    app.dependency_overrides[get_organization_creation_service] = lambda: service

    if authenticated:
        app.dependency_overrides[get_current_user] = build_current_user

    return TestClient(app)


def test_creation_returns_committed_public_projection():
    service = RecordingOrganizationCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations",
            json={
                "name": "  Özdemir Yazılım  ",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "organization": {
            "organization_id": 100,
            "name": "Özdemir Yazılım",
            "is_active": True,
        },
        "own_membership": {
            "membership_id": 200,
            "organization_id": 100,
            "role": "owner",
            "is_active": True,
        },
    }
    assert service.calls == [
        (
            42,
            "Özdemir Yazılım",
        )
    ]
    assert "user_id" not in response.text
    assert "password" not in response.text
    assert UUID(response.headers["x-request-id"]).version == 4


def test_missing_authentication_is_rejected_before_service_call():
    service = RecordingOrganizationCreationService()

    with build_client(
        service,
        authenticated=False,
    ) as client:
        response = client.post(
            "/organizations",
            json={
                "name": "Acme",
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
    assert service.calls == []


def test_actor_becoming_unavailable_returns_401():
    service = RecordingOrganizationCreationService(
        error=OrganizationActorUnavailableError(),
    )

    with build_client(service) as client:
        response = client.post(
            "/organizations",
            json={
                "name": "Acme",
            },
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"


def test_recognized_concurrency_failure_returns_fixed_503():
    service = RecordingOrganizationCreationService(
        error=OrganizationCreationBusyError(),
    )

    with build_client(service) as client:
        response = client.post(
            "/organizations",
            json={
                "name": "Acme",
            },
        )

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "concurrency_busy",
            "message": ("The operation is temporarily busy. Please try again."),
            "details": [],
        }
    }
    assert "retry-after" not in response.headers


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": 123},
        {"name": "   "},
        {"name": "Acme", "user_id": 99},
        {"name": "Acme", "role": "owner"},
        {"name": "Acme", "is_active": True},
    ],
)
def test_invalid_input_never_calls_service(payload):
    service = RecordingOrganizationCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations",
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert service.calls == []


def test_unexpected_failure_remains_safe_internal_error():
    service = RecordingOrganizationCreationService(
        error=RuntimeError(SECRET),
    )

    with build_client(service) as client:
        response = client.post(
            "/organizations",
            json={
                "name": "Acme",
            },
        )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": [],
        }
    }
    assert SECRET not in response.text
