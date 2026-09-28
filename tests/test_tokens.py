from datetime import UTC, datetime

import jwt
import pytest
from pydantic import ValidationError

from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import (
    ACCESS_TOKEN_TTL_SECONDS,
    ALGORITHM,
    AUDIENCE,
    ISSUER,
    MAX_USER_ID,
    AccessTokenIssuer,
)


def test_token_settings_load_secret_from_environment(monkeypatch):
    secret = "a" * 32
    monkeypatch.setenv("OPSDESK_JWT_SECRET", secret)

    settings = TokenSettings()

    assert settings.secret.get_secret_value() == secret
    assert secret not in repr(settings)


def test_token_settings_reject_short_secret_without_disclosure():
    secret = "short-secret-marker"

    with pytest.raises(ValidationError) as exc_info:
        TokenSettings(secret=secret)

    assert secret not in str(exc_info.value)


def test_access_token_contains_only_reviewed_claims():
    secret = "b" * 32
    fixed_now = datetime(2026, 9, 26, 9, 30, tzinfo=UTC)
    issued_at = int(fixed_now.timestamp())

    issuer = AccessTokenIssuer(
        TokenSettings(secret=secret),
        clock=lambda: fixed_now,
    )

    token = issuer.issue(42)

    header = jwt.get_unverified_header(token)
    claims = jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={
            "verify_exp": False,
            "verify_iat": False,
        },
    )

    assert header["alg"] == "HS256"
    assert claims == {
        "sub": "42",
        "iat": issued_at,
        "exp": issued_at + ACCESS_TOKEN_TTL_SECONDS,
        "iss": ISSUER,
        "aud": AUDIENCE,
    }


@pytest.mark.parametrize(
    "invalid_user_id",
    [
        0,
        -1,
        MAX_USER_ID + 1,
    ],
)
def test_access_token_rejects_invalid_user_id(invalid_user_id):
    issuer = AccessTokenIssuer(
        TokenSettings(secret="c" * 32),
    )

    with pytest.raises(
        ValueError,
        match=r"^User ID is outside the supported range\.$",
    ):
        issuer.issue(invalid_user_id)


def test_access_token_rejects_naive_clock():
    issuer = AccessTokenIssuer(
        TokenSettings(secret="d" * 32),
        clock=lambda: datetime(2026, 9, 26, 9, 30),
    )

    with pytest.raises(
        RuntimeError,
        match=r"^Token clock must be timezone-aware\.$",
    ):
        issuer.issue(42)
