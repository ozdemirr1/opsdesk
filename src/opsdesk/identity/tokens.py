from collections.abc import Callable
from datetime import UTC, datetime

import jwt

from opsdesk.identity.token_config import TokenSettings

ALGORITHM = "HS256"
ISSUER = "opsdesk"
AUDIENCE = "opsdesk-api"
ACCESS_TOKEN_TTL_SECONDS = 1800
MAX_USER_ID = 9_223_372_036_854_775_807
REQUIRED_CLAIMS = frozenset(
    {
        "sub",
        "iat",
        "exp",
        "iss",
        "aud",
    }
)

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class AccessTokenIssuer:
    def __init__(
        self,
        settings: TokenSettings,
        clock: Clock = utc_now,
    ) -> None:
        self._settings = settings
        self._clock = clock

    def issue(self, user_id: int) -> str:
        if not 1 <= user_id <= MAX_USER_ID:
            raise ValueError("User ID is outside the supported range.")

        now = self._clock()

        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("Token clock must be timezone-aware.")

        issued_at = int(now.timestamp())

        claims = {
            "sub": str(user_id),
            "iat": issued_at,
            "exp": issued_at + ACCESS_TOKEN_TTL_SECONDS,
            "iss": ISSUER,
            "aud": AUDIENCE,
        }

        return jwt.encode(
            claims,
            self._settings.secret.get_secret_value(),
            algorithm=ALGORITHM,
        )


class InvalidAccessTokenError(Exception):
    pass


class AccessTokenValidator:
    def __init__(
        self,
        settings: TokenSettings,
        clock: Clock = utc_now,
    ) -> None:
        self._settings = settings
        self._clock = clock

    def validate_and_get_user_id(self, token: str) -> int:
        now = self._clock()

        if now.tzinfo is None or now.utcoffset() is None:
            raise RuntimeError("Token clock must be timezone-aware.")

        now_seconds = int(now.timestamp())

        try:
            claims = jwt.decode(
                token,
                self._settings.secret.get_secret_value(),
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                options={
                    "require": sorted(REQUIRED_CLAIMS),
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_sub": False,
                    "strict_aud": True,
                },
            )

            return self._validate_claims(
                claims,
                now_seconds=now_seconds,
            )
        except (
            jwt.PyJWTError,
            TypeError,
            ValueError,
        ):
            raise InvalidAccessTokenError from None

    @staticmethod
    def _validate_claims(
        claims: dict[str, object],
        *,
        now_seconds: int,
    ) -> int:
        if set(claims) != REQUIRED_CLAIMS:
            raise ValueError("Unexpected token claims.")

        subject = claims["sub"]

        if (
            type(subject) is not str
            or not subject.isascii()
            or not subject.isdecimal()
            or subject.startswith("0")
        ):
            raise ValueError("Invalid token subject.")

        user_id = int(subject)

        if not 1 <= user_id <= MAX_USER_ID:
            raise ValueError("Invalid token subject.")

        issued_at = claims["iat"]
        expires_at = claims["exp"]

        if type(issued_at) is not int or type(expires_at) is not int:
            raise ValueError("Invalid token timestamps.")

        if issued_at < 0:
            raise ValueError("Invalid token timestamps.")

        if expires_at != issued_at + ACCESS_TOKEN_TTL_SECONDS:
            raise ValueError("Invalid token lifetime.")

        if issued_at > now_seconds:
            raise ValueError("Token was issued in the future.")

        if now_seconds >= expires_at:
            raise ValueError("Token has expired.")

        return user_id
