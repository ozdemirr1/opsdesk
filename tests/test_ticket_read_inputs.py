import pytest
from pydantic import ValidationError

from opsdesk.tickets.read_models import TicketFilters
from opsdesk.tickets.read_schemas import BIGINT_MAX, TicketListQuery


def test_defaults_and_filters():
    query = TicketListQuery.model_validate({})
    assert (query.limit, query.offset, query.to_filters()) == (20, 0, TicketFilters())


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", None),
        ("  ", None),
        ("  EMAIL  ", "EMAIL"),
        ("İlk  satır", "İlk  satır"),
        ("e\u0301", "e\u0301"),
        ("%_!\\'", "%_!\\'"),
        ("null", "null"),
        ("%25", "%25"),
        ("a" * 255, "a" * 255),
    ],
)
def test_search_preserves_literal_text(value, expected):
    assert TicketListQuery(q=value).q == expected


@pytest.mark.parametrize(
    "value",
    ["a" * 256, " " * 256, "\temail", "email\n", "a\rb", "a\x00b", 12, True, []],
)
def test_search_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        TicketListQuery(q=value)


@pytest.mark.parametrize(
    "payload",
    [
        {"limit": "0"},
        {"limit": "101"},
        {"limit": True},
        {"offset": "-1"},
        {"offset": str(BIGINT_MAX + 1)},
        {"offset": "9" * 5000},
        {"limit": "+1"},
        {"limit": " 1"},
        {"limit": "1.0"},
        {"limit": "1e1"},
        {"limit": "١"},
        {"status": "OPEN"},
        {"status": "all"},
        {"status": ""},
        {"priority": "critical"},
        {"assignment": "all"},
        {"assignment": "unassigned", "assignee_membership_id": "2"},
        {"assignee_membership_id": "0"},
        {"assignee_membership_id": str(BIGINT_MAX + 1)},
        {"role": "owner"},
    ],
)
def test_invalid_query_is_rejected(payload):
    with pytest.raises(ValidationError):
        TicketListQuery.model_validate(payload)


def test_numeric_bounds_leading_zeroes_and_combined_filters():
    query = TicketListQuery.model_validate(
        {
            "q": "email",
            "status": "open",
            "priority": "urgent",
            "assignment": "assigned",
            "assignee_membership_id": str(BIGINT_MAX),
            "limit": "00100",
            "offset": str(BIGINT_MAX),
        }
    )
    assert query.limit == 100
    assert query.offset == BIGINT_MAX
    assert query.to_filters() == TicketFilters(
        "email", "open", "urgent", "assigned", BIGINT_MAX
    )
    assert TicketListQuery(offset="0" * 5000).offset == 0
