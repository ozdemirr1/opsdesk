import pytest
from pydantic import ValidationError

from opsdesk.organizations.models import (
    Organization,
    OrganizationList,
    OrganizationListItem,
    OrganizationMembership,
)
from opsdesk.organizations.schemas import (
    OrganizationListQuery,
    OrganizationListResponse,
    OrganizationProfile,
)


def test_list_query_uses_reviewed_defaults():
    query = OrganizationListQuery.model_validate({})

    assert query.is_active is None
    assert query.limit == 20
    assert query.offset == 0


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        ("false", False),
    ],
)
def test_list_query_accepts_only_exact_lowercase_boolean(
    raw_value,
    expected,
):
    query = OrganizationListQuery.model_validate(
        {
            "is_active": raw_value,
        }
    )

    assert query.is_active is expected


@pytest.mark.parametrize(
    "raw_value",
    [
        "True",
        "False",
        "TRUE",
        "FALSE",
        "1",
        "0",
        "yes",
        "on",
        " true ",
        "",
        True,
        False,
    ],
)
def test_list_query_rejects_other_boolean_representations(raw_value):
    with pytest.raises(ValidationError):
        OrganizationListQuery.model_validate(
            {
                "is_active": raw_value,
            }
        )


@pytest.mark.parametrize(
    ("limit", "offset"),
    [
        ("1", "0"),
        ("20", "10"),
        ("100", "999"),
        (1, 0),
        (100, 999),
    ],
)
def test_list_query_accepts_valid_pagination(limit, offset):
    query = OrganizationListQuery.model_validate(
        {
            "limit": limit,
            "offset": offset,
        }
    )

    assert query.limit == int(limit)
    assert query.offset == int(offset)


@pytest.mark.parametrize(
    "payload",
    [
        {"limit": "0"},
        {"limit": "101"},
        {"limit": "-1"},
        {"limit": "1.5"},
        {"limit": True},
        {"offset": "-1"},
        {"offset": "1.5"},
        {"offset": False},
        {"unknown": "value"},
    ],
)
def test_list_query_rejects_invalid_pagination_and_unknown_fields(payload):
    with pytest.raises(ValidationError):
        OrganizationListQuery.model_validate(payload)


def test_list_response_exposes_only_reviewed_projection():
    result = OrganizationList(
        items=(
            OrganizationListItem(
                organization=Organization(
                    organization_id=100,
                    name="Acme",
                    is_active=False,
                ),
                own_membership=OrganizationMembership(
                    membership_id=200,
                    user_id=42,
                    organization_id=100,
                    role="agent",
                    is_active=True,
                ),
            ),
        ),
        total_count=1,
        limit=20,
        offset=0,
    )

    response = OrganizationListResponse.model_validate(result)

    assert response.model_dump(mode="json") == {
        "items": [
            {
                "organization": {
                    "organization_id": 100,
                    "name": "Acme",
                    "is_active": False,
                },
                "own_membership": {
                    "membership_id": 200,
                    "organization_id": 100,
                    "role": "agent",
                    "is_active": True,
                },
            }
        ],
        "total_count": 1,
        "limit": 20,
        "offset": 0,
    }
    assert "user_id" not in response.model_dump_json()


def test_detail_response_contains_only_organization_profile():
    response = OrganizationProfile.model_validate(
        Organization(
            organization_id=100,
            name="Acme",
            is_active=True,
        )
    )

    assert response.model_dump() == {
        "organization_id": 100,
        "name": "Acme",
        "is_active": True,
    }
