from dataclasses import replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from tests.test_comment_service import ACCESS, TICKET

from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_current_user
from opsdesk.main import create_app
from opsdesk.tickets.dependencies import get_ticket_priority_service
from opsdesk.tickets.priority import (
    PriorityBusyError,
    PriorityPermissionError,
    PriorityStateError,
    TicketPriorityContext,
    TicketPriorityService,
)
from opsdesk.tickets.repositories import TicketConcurrencyError
from opsdesk.tickets.services import TicketNotFoundError

ARGS = dict(actor_user_id=42, organization_id=10, ticket_id=20, priority="high")
PATH = "/organizations/10/tickets/20/priority"


def subject(role="agent", state="open", priority="medium", own=True):
    repo, tx = Mock(), Mock()
    member = replace(ACCESS.actor_membership, role=role)
    repo.lock_context.return_value = TicketPriorityContext(
        replace(ACCESS, actor_membership=member),
        replace(
            TICKET,
            status=state,
            priority=priority,
            requester_membership_id=40 if own else 99,
        ),
    )
    repo.set_priority.return_value = replace(TICKET, priority="high")
    return TicketPriorityService(repo, tx), repo, tx


@pytest.mark.parametrize("role", ["agent", "admin", "owner"])
@pytest.mark.parametrize("state", ["open", "in_progress"])
@pytest.mark.parametrize("same", [False, True])
def test_staff_mutations_and_authorized_noops(role, state, same):
    service, repo, tx = subject(role, state, "high" if same else "medium", own=False)
    result = service.change(**ARGS)
    assert result.priority == "high"
    assert repo.set_priority.call_count == int(not same)
    tx.commit.assert_called_once()
    tx.rollback.assert_not_called()


@pytest.mark.parametrize(
    "role,state,own,error",
    [
        ("customer", "open", True, PriorityPermissionError),
        ("customer", "closed", True, PriorityPermissionError),
        ("customer", "open", False, TicketNotFoundError),
        ("agent", "resolved", True, PriorityStateError),
        ("owner", "closed", True, PriorityStateError),
    ],
)
def test_same_value_does_not_bypass_denials(role, state, own, error):
    service, repo, tx = subject(role, state, "high", own)
    with pytest.raises(error):
        service.change(**ARGS)
    repo.set_priority.assert_not_called()
    tx.commit.assert_not_called()
    tx.rollback.assert_called_once()


@pytest.mark.parametrize("stage", ["lock_context", "set_priority", "commit"])
@pytest.mark.parametrize(
    "error,expected",
    [(TicketConcurrencyError, PriorityBusyError), (RuntimeError, RuntimeError)],
)
def test_failures_rollback(stage, error, expected):
    service, repo, tx = subject()
    getattr(tx if stage == "commit" else repo, stage).side_effect = error
    with pytest.raises(expected):
        service.change(**ARGS)
    tx.rollback.assert_called_once()


@pytest.fixture
def api():
    app = create_app(Settings(environment="test"))
    service = Mock()
    service.change.return_value = replace(TICKET, priority="high")
    app.dependency_overrides[get_current_user] = lambda: ACCESS.actor_user
    app.dependency_overrides[get_ticket_priority_service] = lambda: service
    with TestClient(app) as client:
        yield client, service, app


def test_api_derives_actor(api):
    client, service, _ = api
    response = client.put(PATH, json={"priority": "high"})
    assert response.status_code == 200
    assert response.json()["priority"] == "high"
    service.change.assert_called_once_with(**ARGS)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"priority": None},
        {"priority": True},
        {"priority": 1},
        {"priority": ""},
        {"priority": "HIGH"},
        {"priority": " high "},
        {"priority": "private-marker"},
        {"priority": "high", "actor_user_id": 999},
        {"priority": "high", "status": "closed"},
    ],
)
def test_invalid_body_rejected(api, body):
    client, service, _ = api
    response = client.put(PATH, json=body)
    assert response.status_code == 422 and "private-marker" not in response.text
    service.change.assert_not_called()


def test_anonymous_request_denied(api):
    client, service, app = api
    del app.dependency_overrides[get_current_user]
    assert client.put(PATH, json={"priority": "high"}).status_code == 401
    service.change.assert_not_called()


@pytest.mark.parametrize(
    "error,status,code",
    [
        (PriorityPermissionError, 403, "permission_denied"),
        (PriorityStateError, 409, "state_conflict"),
        (PriorityBusyError, 503, "concurrency_busy"),
    ],
)
def test_safe_api_errors(api, error, status, code):
    client, service, _ = api
    service.change.side_effect = error("private-marker")
    response = client.put(PATH, json={"priority": "high"})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["details"] == []
    assert "private-marker" not in response.text
