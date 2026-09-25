from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from opsdesk.identity.normalization import normalize_email, normalize_password
from opsdesk.identity.schemas import RegisterUserRequest, UserProfile


def test_email_normalization_trims_and_lowercases():
    assert normalize_email("  TEST@EXAMPLE.COM  ") == "test@example.com"


def test_email_normalization_preserves_dots_and_tags():
    assert normalize_email("user.name+tag@example.com") == "user.name+tag@example.com"


def test_email_normalization_enforces_exact_254_character_boundary():
    local_part = "a" * 64
    accepted_domain = ".".join(("b" * 63, "c" * 63, "d" * 61))
    rejected_domain = ".".join(("b" * 63, "c" * 63, "d" * 62))

    accepted_email = f"{local_part}@{accepted_domain}"
    rejected_email = f"{local_part}@{rejected_domain}"

    assert len(accepted_email) == 254
    assert len(rejected_email) == 255
    assert normalize_email(accepted_email) == accepted_email

    with pytest.raises(ValueError, match=r"^Invalid email\.$"):
        normalize_email(rejected_email)


@pytest.mark.parametrize(
    "invalid_email",
    [
        "türkçe@example.com",
        "John Doe <john@example.com>",
        "admin@localhost",
        "a" * 244 + "@example.com",
    ],
)
def test_email_normalization_rejects_invalid_formats(invalid_email):
    with pytest.raises(ValueError, match=r"^Invalid email\.$"):
        normalize_email(invalid_email)


def test_password_normalization_accepts_valid_lengths():
    assert normalize_password("a" * 15) == "a" * 15
    assert normalize_password("a" * 128) == "a" * 128


@pytest.mark.parametrize(
    "invalid_password",
    [
        "a" * 14,
        "a" * 129,
    ],
)
def test_password_normalization_rejects_invalid_lengths(invalid_password):
    with pytest.raises(ValueError, match=r"^Invalid password\.$"):
        normalize_password(invalid_password)


def test_password_normalization_applies_nfc():
    nfd_password = "e\u0301" + "a" * 14
    expected_nfc = "\u00e9" + "a" * 14
    assert normalize_password(nfd_password) == expected_nfc


def test_password_normalization_preserves_spaces_and_case():
    password_with_spaces_and_case = "My Secret Pass 123"
    assert (
        normalize_password(password_with_spaces_and_case)
        == password_with_spaces_and_case
    )


def test_password_normalization_rejects_unpaired_surrogate():
    with pytest.raises(ValueError, match=r"^Invalid password\.$"):
        normalize_password("a" * 14 + "\ud800")


def test_register_user_request_requires_both_fields():
    with pytest.raises(ValidationError):
        RegisterUserRequest(email="test@example.com")

    with pytest.raises(ValidationError):
        RegisterUserRequest(password="a" * 15)


@pytest.mark.parametrize("invalid_value", [None, True, 123, [], {}])
@pytest.mark.parametrize("field_name", ["email", "password"])
def test_register_user_request_rejects_wrong_field_types(
    field_name,
    invalid_value,
):
    request_data = {
        "email": "test@example.com",
        "password": "a" * 15,
    }
    request_data[field_name] = invalid_value

    with pytest.raises(ValidationError):
        RegisterUserRequest(**request_data)


@pytest.mark.parametrize("field_name", ["role", "user_id", "is_active"])
def test_register_user_request_rejects_server_controlled_fields(field_name):
    request_data = {
        "email": "test@example.com",
        "password": "a" * 15,
        field_name: "client-controlled-value",
    }

    with pytest.raises(ValidationError):
        RegisterUserRequest(**request_data)


def test_user_profile_projects_only_public_attributes():
    stored_user = SimpleNamespace(
        user_id=1,
        email="test@example.com",
        password_hash="$argon2id$sensitive-hash",
        is_active=True,
    )

    profile = UserProfile.model_validate(stored_user)
    dumped_data = profile.model_dump()

    assert "password" not in dumped_data
    assert "password_hash" not in dumped_data
    assert dumped_data == {"user_id": 1, "email": "test@example.com", "is_active": True}
