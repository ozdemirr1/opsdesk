from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.main import create_app
from opsdesk.tickets.dependencies import (
    get_ticket_creation_service,
)
from opsdesk.tickets.models import Ticket
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketCreationBusyError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)

FIXED_TIME = datetime(
    2026,
    10,
    5,
    16,
    30,
    45,
    123456,
    tzinfo=UTC,
)
SECRET = "synthetic-private-ticket-marker"


def build_current_user() -> User:
    return User(
        user_id=42,
        email="actor@example.com",
        password_hash="private-password-hash",
        is_active=True,
    )


class RecordingTicketCreationService:
    def __init__(
        self,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        title: str,
        description: str,
        priority: str,
    ) -> Ticket:
        self.calls.append(
            {
                "actor_user_id": actor_user_id,
                "organization_id": organization_id,
                "title": title,
                "description": description,
                "priority": priority,
            }
        )

        if self.error is not None:
            raise self.error

        return Ticket(
            ticket_id=300,
            organization_id=organization_id,
            requester_membership_id=200,
            creator_membership_id=200,
            assignee_membership_id=None,
            title=title,
            description=description,
            status="open",
            priority=priority,
            created_at=FIXED_TIME,
            updated_at=FIXED_TIME,
        )


def build_client(
    service: RecordingTicketCreationService,
    *,
    authenticated: bool = True,
) -> TestClient:
    app = create_app(Settings(environment="test"))

    app.dependency_overrides[get_ticket_creation_service] = lambda: service

    if authenticated:
        app.dependency_overrides[get_current_user] = build_current_user

    return TestClient(app)


def valid_payload() -> dict[str, object]:
    return {
        "title": "  Login problem  ",
        "description": (
            "  Traceback:\n    Connection refused\n  Please investigate.  "
        ),
    }


def test_creation_returns_committed_public_projection():
    service = RecordingTicketCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=valid_payload(),
        )

    assert response.status_code == 201
    assert response.json() == {
        "ticket_id": 300,
        "organization_id": 100,
        "requester_membership_id": 200,
        "creator_membership_id": 200,
        "assignee_membership_id": None,
        "title": "Login problem",
        "description": ("Traceback:\n    Connection refused\n  Please investigate."),
        "status": "open",
        "priority": "medium",
        "created_at": "2026-10-05T16:30:45.123456Z",
        "updated_at": "2026-10-05T16:30:45.123456Z",
    }
    assert service.calls == [
        {
            "actor_user_id": 42,
            "organization_id": 100,
            "title": "Login problem",
            "description": (
                "Traceback:\n    Connection refused\n  Please investigate."
            ),
            "priority": "medium",
        }
    ]
    assert UUID(response.headers["x-request-id"]).version == 4
    assert "password" not in response.text


def test_explicit_priority_is_forwarded():
    service = RecordingTicketCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json={
                "title": "Urgent outage",
                "description": "Production is unavailable.",
                "priority": "urgent",
            },
        )

    assert response.status_code == 201
    assert service.calls[0]["priority"] == "urgent"
    assert response.json()["priority"] == "urgent"


@pytest.mark.parametrize(
    "field_name",
    [
        "ticket_id",
        "organization_id",
        "requester_membership_id",
        "creator_membership_id",
        "assignee_membership_id",
        "status",
        "created_at",
        "updated_at",
        "assignee",
        "unknown",
    ],
)
def test_server_owned_and_unknown_fields_never_call_service(
    field_name,
):
    service = RecordingTicketCreationService()
    payload = valid_payload()
    payload[field_name] = None

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert service.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "description": "Description",
        },
        {
            "title": "Title",
        },
        {
            "title": "Title\nwith newline",
            "description": "Description",
        },
        {
            "title": "Title",
            "description": "\x00Invalid",
        },
        {
            "title": "Title",
            "description": "Description",
            "priority": None,
        },
        {
            "title": "Title",
            "description": "Description",
            "priority": "HIGH",
        },
    ],
)
def test_invalid_payload_never_calls_service(payload):
    service = RecordingTicketCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=payload,
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert service.calls == []


def test_invalid_organization_identifier_never_calls_service():
    service = RecordingTicketCreationService()

    with build_client(service) as client:
        response = client.post(
            "/organizations/0/tickets",
            json=valid_payload(),
        )

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == ("path.organization_id")
    assert service.calls == []


def test_missing_authentication_is_rejected_before_service():
    service = RecordingTicketCreationService()

    with build_client(
        service,
        authenticated=False,
    ) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=valid_payload(),
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (
            TicketActorUnavailableError(),
            401,
            "unauthenticated",
        ),
        (
            TicketOrganizationAccessDeniedError(),
            403,
            "organization_access_denied",
        ),
        (
            TicketOrganizationSuspendedError(),
            403,
            "organization_suspended",
        ),
        (
            TicketCreationBusyError(),
            503,
            "concurrency_busy",
        ),
    ],
)
def test_domain_errors_use_fixed_public_responses(
    error,
    status_code,
    error_code,
):
    service = RecordingTicketCreationService(error=error)

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=valid_payload(),
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert response.json()["error"]["details"] == []

    if status_code == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_unexpected_failure_remains_safe_internal_error():
    service = RecordingTicketCreationService(
        error=RuntimeError(SECRET),
    )

    with build_client(service) as client:
        response = client.post(
            "/organizations/100/tickets",
            json=valid_payload(),
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
