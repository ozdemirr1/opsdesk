from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.main import create_app
from opsdesk.tickets.dependencies import get_ticket_read_service
from opsdesk.tickets.models import Ticket
from opsdesk.tickets.read_models import TicketFilters, TicketList
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
    TicketReadBusyError,
)


class RecordingService:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def get_for_actor(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        now = datetime(2026, 10, 26, tzinfo=UTC)
        return Ticket(
            kwargs["ticket_id"],
            kwargs["organization_id"],
            8,
            8,
            None,
            "Title",
            "Description",
            "closed",
            "low",
            now,
            now,
        )

    def list_for_actor(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return TicketList((), 12, kwargs["limit"], kwargs["offset"])


def client_for(service, authenticated=True):
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_ticket_read_service] = lambda: service
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: User(
            42, "reader@example.com", "private-hash", True
        )
    return TestClient(app, raise_server_exceptions=False)


def test_list_envelope_and_query_forwarding():
    service = RecordingService()
    with client_for(service) as client:
        response = client.get(
            "/organizations/2/tickets",
            params={"q": "  EMAIL  ", "status": "closed", "offset": "20"},
        )
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total_count": 12,
        "limit": 20,
        "offset": 20,
    }
    assert service.calls == [
        {
            "actor_user_id": 42,
            "organization_id": 2,
            "filters": TicketFilters(q="EMAIL", status="closed"),
            "limit": 20,
            "offset": 20,
        }
    ]


def test_detail_has_explicit_public_projection():
    with client_for(RecordingService()) as client:
        response = client.get("/organizations/2/tickets/3")
    assert response.status_code == 200
    assert response.json() == {
        "ticket_id": 3,
        "organization_id": 2,
        "requester_membership_id": 8,
        "creator_membership_id": 8,
        "assignee_membership_id": None,
        "title": "Title",
        "description": "Description",
        "status": "closed",
        "priority": "low",
        "created_at": "2026-10-26T00:00:00Z",
        "updated_at": "2026-10-26T00:00:00Z",
    }
    assert "private" not in response.text
    assert "x-request-id" in response.headers


@pytest.mark.parametrize(
    "path", ["/organizations/2/tickets", "/organizations/2/tickets/3"]
)
def test_missing_auth_does_not_call_service(path):
    service = RecordingService()
    with client_for(service, authenticated=False) as client:
        response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert service.calls == []


@pytest.mark.parametrize(
    "suffix",
    [
        "?q=a&q=a",
        "?limit=20&limit=20",
        "?private-marker=value",
        "?q=%00private-marker",
        "?q=%09private-marker",
        "?status=all",
        "?limit=0",
        "?offset=9223372036854775808",
        "?assignment=unassigned&assignee_membership_id=8",
        "/3?limit=20",
        "/0",
        "/9223372036854775808",
    ],
)
def test_invalid_requests_fail_safely_before_read(suffix):
    service = RecordingService()
    with client_for(service) as client:
        response = client.get("/organizations/2/tickets" + suffix)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "private-marker" not in response.text
    assert service.calls == []


@pytest.mark.parametrize(
    "path", ["/organizations/2/tickets", "/organizations/2/tickets/3"]
)
@pytest.mark.parametrize(
    "error,status,code",
    [
        (TicketActorUnavailableError(), 401, "unauthenticated"),
        (TicketOrganizationAccessDeniedError(), 403, "organization_access_denied"),
        (TicketOrganizationSuspendedError(), 403, "organization_suspended"),
        (TicketReadBusyError(), 503, "concurrency_busy"),
        (RuntimeError("secret-sql"), 500, "internal_error"),
    ],
)
def test_safe_error_mapping(path, error, status, code):
    with client_for(RecordingService(error)) as client:
        response = client.get(path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "secret-sql" not in response.text
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


def test_missing_hidden_and_foreign_detail_share_not_found_mapping():
    with client_for(RecordingService(TicketNotFoundError())) as client:
        response = client.get("/organizations/2/tickets/3")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "ticket_not_found",
            "message": "Ticket not found.",
            "details": [],
        }
    }
