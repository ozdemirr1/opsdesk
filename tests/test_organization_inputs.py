import pytest
from pydantic import ValidationError

from opsdesk.organizations.normalization import normalize_organization_name
from opsdesk.organizations.schemas import CreateOrganizationRequest


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("Acme", "Acme"),
        ("  Özdemir Yazılım  ", "Özdemir Yazılım"),
        ("Özdemir  Yazılım", "Özdemir  Yazılım"),
        ("\u00a0Acme\u00a0", "Acme"),
        ("A" * 255, "A" * 255),
    ],
)
def test_valid_organization_names_are_normalized(
    raw_name,
    expected,
):
    assert normalize_organization_name(raw_name) == expected


@pytest.mark.parametrize(
    "raw_name",
    [
        "",
        "   ",
        "\u00a0",
        "A" * 256,
        "\tAcme",
        "Acme\n",
        "Acme\rTeam",
        "Acme\x00Team",
    ],
)
def test_invalid_organization_names_are_rejected(raw_name):
    with pytest.raises(
        ValueError,
        match="^Invalid organization name\\.$",
    ):
        normalize_organization_name(raw_name)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": None},
        {"name": 123},
        {"name": "Acme", "role": "owner"},
        {"name": "Acme", "user_id": 42},
        {"name": "Acme", "is_active": True},
    ],
)
def test_request_rejects_missing_wrong_and_server_owned_fields(payload):
    with pytest.raises(ValidationError):
        CreateOrganizationRequest.model_validate(payload)


def test_request_exposes_only_normalized_name():
    request = CreateOrganizationRequest.model_validate(
        {
            "name": "  Özdemir Yazılım  ",
        }
    )

    assert request.model_dump() == {
        "name": "Özdemir Yazılım",
    }
