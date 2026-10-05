from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from opsdesk.tickets.models import Ticket
from opsdesk.tickets.normalization import (
    normalize_ticket_description,
    normalize_ticket_title,
)
from opsdesk.tickets.schemas import (
    CreateTicketRequest,
    TicketResponse,
)


@pytest.mark.parametrize(
    ("raw_title", "expected"),
    [
        ("Login problem", "Login problem"),
        ("  Login problem  ", "Login problem"),
        ("\u00a0Login problem\u00a0", "Login problem"),
        ("Login  problem", "Login  problem"),
        ("A", "A"),
        ("A" * 255, "A" * 255),
    ],
)
def test_valid_titles_are_normalized(raw_title, expected):
    assert normalize_ticket_title(raw_title) == expected


@pytest.mark.parametrize(
    "raw_title",
    [
        "",
        " ",
        "\u00a0",
        "A" * 256,
        "Login\tproblem",
        "Login\nproblem",
        "Login\rproblem",
        "Login\x00problem",
        "\tLogin problem",
        "Login problem\n",
    ],
)
def test_invalid_titles_are_rejected_before_or_after_trimming(
    raw_title,
):
    with pytest.raises(
        ValueError,
        match="^Invalid ticket title\\.$",
    ):
        normalize_ticket_title(raw_title)


@pytest.mark.parametrize(
    ("raw_description", "expected"),
    [
        ("Connection failed.", "Connection failed."),
        (
            "  Traceback:\n    Connection refused\n  Retry failed.  ",
            "Traceback:\n    Connection refused\n  Retry failed.",
        ),
        ("Description\twith tab", "Description\twith tab"),
        ("Description\rwith carriage return", "Description\rwith carriage return"),
        ("A", "A"),
        ("A" * 10_000, "A" * 10_000),
    ],
)
def test_valid_descriptions_preserve_internal_formatting(
    raw_description,
    expected,
):
    assert normalize_ticket_description(raw_description) == expected


@pytest.mark.parametrize(
    "raw_description",
    [
        "",
        " ",
        "\t\n\r",
        "A" * 10_001,
        "Description\x00with NUL",
        "\x00Description",
    ],
)
def test_invalid_descriptions_are_rejected(raw_description):
    with pytest.raises(
        ValueError,
        match="^Invalid ticket description\\.$",
    ):
        normalize_ticket_description(raw_description)


@pytest.mark.parametrize(
    "priority",
    [
        "low",
        "medium",
        "high",
        "urgent",
    ],
)
def test_request_accepts_exact_priority_values(priority):
    request = CreateTicketRequest.model_validate(
        {
            "title": "Login problem",
            "description": "Login is unavailable.",
            "priority": priority,
        }
    )

    assert request.priority == priority


def test_omitted_priority_defaults_to_medium():
    request = CreateTicketRequest.model_validate(
        {
            "title": "  Login problem  ",
            "description": "  Login is unavailable.  ",
        }
    )

    assert request.model_dump() == {
        "title": "Login problem",
        "description": "Login is unavailable.",
        "priority": "medium",
    }


@pytest.mark.parametrize(
    "priority",
    [
        None,
        "",
        "HIGH",
        " high",
        "high ",
        "normal",
        1,
        True,
    ],
)
def test_request_rejects_invalid_priority(priority):
    with pytest.raises(ValidationError):
        CreateTicketRequest.model_validate(
            {
                "title": "Login problem",
                "description": "Login is unavailable.",
                "priority": priority,
            }
        )


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
def test_request_rejects_every_server_owned_or_unknown_field(
    field_name,
):
    payload = {
        "title": "Login problem",
        "description": "Login is unavailable.",
        field_name: None,
    }

    with pytest.raises(ValidationError):
        CreateTicketRequest.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"description": "Description"},
        {"title": "Title"},
        {"title": None, "description": "Description"},
        {"title": 123, "description": "Description"},
        {"title": "Title", "description": None},
        {"title": "Title", "description": 123},
    ],
)
def test_request_rejects_missing_null_and_non_string_text(payload):
    with pytest.raises(ValidationError):
        CreateTicketRequest.model_validate(payload)


def test_response_contains_the_complete_public_ticket_projection():
    timestamp = datetime(
        2026,
        10,
        5,
        12,
        30,
        45,
        123456,
        tzinfo=UTC,
    )

    ticket = Ticket(
        ticket_id=300,
        organization_id=100,
        requester_membership_id=200,
        creator_membership_id=200,
        assignee_membership_id=None,
        title="Login problem",
        description="Login is unavailable.",
        status="open",
        priority="medium",
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = TicketResponse.model_validate(ticket)

    assert response.model_dump(mode="json") == {
        "ticket_id": 300,
        "organization_id": 100,
        "requester_membership_id": 200,
        "creator_membership_id": 200,
        "assignee_membership_id": None,
        "title": "Login problem",
        "description": "Login is unavailable.",
        "status": "open",
        "priority": "medium",
        "created_at": "2026-10-05T12:30:45.123456Z",
        "updated_at": "2026-10-05T12:30:45.123456Z",
    }
