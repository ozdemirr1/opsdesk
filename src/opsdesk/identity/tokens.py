from collections.abc import Callable
from datetime import UTC, datetime

import jwt

from opsdesk.identity.token_config import TokenSettings

ALGORITHM = "HS256"
ISSUER = "opsdesk"
AUDIENCE = "opsdesk-api"
ACCESS_TOKEN_TTL_SECONDS = 1800
MAX_USER_ID = 9_223_372_036_854_775_807

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
