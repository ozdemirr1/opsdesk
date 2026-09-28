from datetime import UTC, datetime

import jwt
import pytest

from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import (
    ACCESS_TOKEN_TTL_SECONDS,
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    MAX_USER_ID,
    REQUIRED_CLAIMS,
    AccessTokenValidator,
    InvalidAccessTokenError,
)

SECRET = "a" * 64
OTHER_SECRET = "b" * 64
FIXED_NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
NOW_SECONDS = int(FIXED_NOW.timestamp())
VALID_ISSUED_AT = NOW_SECONDS - 300


def valid_claims() -> dict[str, object]:
    return {
        "sub": "42",
        "iat": VALID_ISSUED_AT,
        "exp": VALID_ISSUED_AT + ACCESS_TOKEN_TTL_SECONDS,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }


def encode(
    claims: dict[str, object],
    *,
    secret: str = SECRET,
    algorithm: str = ALGORITHM,
) -> str:
    return jwt.encode(
        claims,
        secret,
        algorithm=algorithm,
    )


def build_validator():
    return AccessTokenValidator(
        TokenSettings(secret=SECRET),
        clock=lambda: FIXED_NOW,
    )


def test_valid_token_returns_canonical_user_id():
    token = encode(valid_claims())

    user_id = build_validator().validate_and_get_user_id(token)

    assert user_id == 42


@pytest.mark.parametrize("missing_claim", sorted(REQUIRED_CLAIMS))
def test_missing_required_claim_is_rejected(missing_claim):
    claims = valid_claims()
    del claims[missing_claim]

    with pytest.raises(InvalidAccessTokenError):
        build_validator().validate_and_get_user_id(
            encode(claims),
        )


@pytest.mark.parametrize(
    ("claim", "invalid_value"),
    [
        ("sub", 42),
        ("sub", ""),
        ("sub", "0"),
        ("sub", "01"),
        ("sub", "+42"),
        ("sub", "-42"),
        ("sub", str(MAX_USER_ID + 1)),
        ("iat", True),
        ("iat", "123"),
        ("iat", -1),
        ("exp", True),
        ("exp", "123"),
        ("iss", "other-issuer"),
        ("aud", "other-audience"),
        ("aud", [AUDIENCE]),
    ],
)
def test_invalid_claim_types_and_values_are_rejected(
    claim,
    invalid_value,
):
    claims = valid_claims()
    claims[claim] = invalid_value

    with pytest.raises(InvalidAccessTokenError):
        build_validator().validate_and_get_user_id(
            encode(claims),
        )


@pytest.mark.parametrize(
    ("issued_at", "expires_at"),
    [
        (
            NOW_SECONDS + 1,
            NOW_SECONDS + 1 + ACCESS_TOKEN_TTL_SECONDS,
        ),
        (
            VALID_ISSUED_AT,
            VALID_ISSUED_AT + ACCESS_TOKEN_TTL_SECONDS + 1,
        ),
        (
            NOW_SECONDS - ACCESS_TOKEN_TTL_SECONDS,
            NOW_SECONDS,
        ),
    ],
)
def test_invalid_time_relationships_are_rejected(
    issued_at,
    expires_at,
):
    claims = valid_claims()
    claims["iat"] = issued_at
    claims["exp"] = expires_at

    with pytest.raises(InvalidAccessTokenError):
        build_validator().validate_and_get_user_id(
            encode(claims),
        )


def test_additional_claim_is_rejected():
    claims = valid_claims()
    claims["jti"] = "unexpected-claim"

    with pytest.raises(InvalidAccessTokenError):
        build_validator().validate_and_get_user_id(
            encode(claims),
        )


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        encode(valid_claims(), secret=OTHER_SECRET),
        encode(valid_claims(), algorithm="HS384"),
    ],
)
def test_malformed_signature_and_algorithm_are_rejected(token):
    with pytest.raises(InvalidAccessTokenError):
        build_validator().validate_and_get_user_id(token)


def test_naive_validation_clock_is_server_error():
    validator = AccessTokenValidator(
        TokenSettings(secret=SECRET),
        clock=lambda: datetime(2026, 9, 28, 12, 0),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Token clock must be timezone-aware\.$",
    ):
        validator.validate_and_get_user_id(
            encode(valid_claims()),
        )
