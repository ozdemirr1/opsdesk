from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from opsdesk.comments.dependencies import get_comment_service
from opsdesk.comments.models import Comment, CommentPage
from opsdesk.comments.schemas import CreateCommentRequest
from opsdesk.comments.services import CommentBusyError, CommentClosedError
from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.main import create_app
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)

PATH = "/organizations/10/tickets/20/comments"
COMMENT = Comment(30, 10, 20, 40, "Hello", datetime(2026, 10, 29, tzinfo=UTC))


@pytest.fixture
def api():
    service = Mock()
    service.create.return_value = COMMENT
    service.list_for_actor.return_value = CommentPage((COMMENT,), 1, 20, 0)
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_comment_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: User(
        42, "demo@example.com", "hash", True
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, service, app


def test_create_derives_actor_and_returns_only_public_fields(api):
    client, service, _ = api
    response = client.post(PATH, json={"content": "  First\r\nSecond\rThird\tline  "})
    assert response.status_code == 201
    assert set(response.json()) == {
        "comment_id",
        "author_membership_id",
        "content",
        "created_at",
    }
    service.create.assert_called_once_with(
        actor_user_id=42,
        organization_id=10,
        ticket_id=20,
        content="First\nSecond\nThird\tline",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"content": None},
        {"content": 12},
        {"content": True},
        {"content": []},
        {"content": ""},
        {"content": " \n\t\u2003"},
        {"content": "x" * 10001},
        {"content": "text", "author_membership_id": 99},
        {"content": "text", "organization_id": 99},
        {"content": "text", "ticket_id": 99},
        {"content": "text", "created_at": "today"},
    ]
    + [
        {"content": chr(i) + "private-marker"}
        for i in range(32)
        if i not in (9, 10, 13)
    ],
)
def test_invalid_content_never_reaches_service_or_leaks_input(api, payload):
    client, service, _ = api
    response = client.post(PATH, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "private-marker" not in response.text
    service.create.assert_not_called()


@pytest.mark.parametrize(
    "content", ["x", "🙂" * 10000, "İlk satır.\nSecond\tline", "a  b"]
)
def test_valid_unicode_and_internal_whitespace(content):
    assert CreateCommentRequest(content=content).content == content


def test_control_character_is_rejected_before_strip():
    with pytest.raises(ValidationError):
        CreateCommentRequest(content="\x0btext")


def test_get_pagination_and_public_projection(api):
    client, service, _ = api
    response = client.get(PATH + "?limit=2&offset=3")
    assert response.status_code == 200
    assert set(response.json()["items"][0]) == {
        "comment_id",
        "author_membership_id",
        "content",
        "created_at",
    }
    service.list_for_actor.assert_called_once_with(
        actor_user_id=42, organization_id=10, ticket_id=20, limit=2, offset=3
    )


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "offset=-1",
        "limit=true",
        "limit=1.0",
        "offset=9223372036854775808",
        "limit=1&limit=2",
        "offset=0&offset=1",
        "secret-marker=value",
        "limit=",
        "offset=",
    ],
)
def test_invalid_pagination_is_safe(api, query):
    client, service, _ = api
    response = client.get(PATH + "?" + query)
    assert response.status_code == 422
    assert "secret-marker" not in response.text
    service.list_for_actor.assert_not_called()


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "path",
    [
        "/organizations/0/tickets/20/comments",
        "/organizations/10/tickets/0/comments",
        "/organizations/10/tickets/9223372036854775808/comments",
    ],
)
def test_invalid_path_ids(api, method, path):
    client, service, _ = api
    assert (
        client.request(
            method, path, **({"json": {"content": "x"}} if method == "post" else {})
        ).status_code
        == 422
    )
    assert not service.mock_calls


@pytest.mark.parametrize("method", ["get", "post"])
def test_authentication_required(api, method):
    client, service, app = api
    del app.dependency_overrides[get_current_user]
    response = client.request(
        method, PATH, **({"json": {"content": "x"}} if method == "post" else {})
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert not service.mock_calls


@pytest.mark.parametrize(
    "error,status,code",
    [
        (TicketActorUnavailableError, 401, "unauthenticated"),
        (TicketOrganizationAccessDeniedError, 403, "organization_access_denied"),
        (TicketOrganizationSuspendedError, 403, "organization_suspended"),
        (TicketNotFoundError, 404, "ticket_not_found"),
        (CommentBusyError, 503, "concurrency_busy"),
        (RuntimeError, 500, "internal_error"),
    ],
)
@pytest.mark.parametrize("method", ["get", "post"])
def test_safe_error_mapping(api, error, status, code, method):
    client, service, _ = api
    getattr(
        service, "create" if method == "post" else "list_for_actor"
    ).side_effect = error("private-marker")
    response = client.request(
        method, PATH, **({"json": {"content": "x"}} if method == "post" else {})
    )
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == []
    assert "private-marker" not in response.text
    assert "retry-after" not in response.headers


def test_closed_ticket_is_conflict(api):
    client, service, _ = api
    service.create.side_effect = CommentClosedError
    response = client.post(PATH, json={"content": "x"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "state_conflict"


def test_transport_errors(api):
    client, service, _ = api
    assert (
        client.post(
            PATH, content="{", headers={"content-type": "application/json"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            PATH, content="x", headers={"content-type": "text/plain"}
        ).status_code
        == 415
    )
    service.create.assert_not_called()
