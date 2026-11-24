"""Opt-in, IP-scoped authentication admission limits."""

import logging
from hashlib import sha256
from ipaddress import ip_address
from math import ceil
from typing import Literal

from fastapi import Request
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from opsdesk.api.errors import ApiError

logger = logging.getLogger("opsdesk.auth_limit")
Operation = Literal["login", "register"]

# Validate existing state before mutation; Lua atomicity does not imply rollback.
SCRIPT = """
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local raw = redis.call('GET', KEYS[1])
if not raw then
    redis.call('SET', KEYS[1], 1, 'PX', window)
    return {1, 1, window}
end
local used = tonumber(raw)
local ttl = redis.call('PTTL', KEYS[1])
if not used or used < 1 or used > limit or used ~= math.floor(used)
    or raw ~= tostring(used) or ttl < 0 or ttl > window then
    return redis.error_reply('Invalid limiter state')
end
if used >= limit then
    return {0, used, ttl}
end
used = redis.call('INCR', KEYS[1])
return {1, used, ttl}
"""


class AuthLimitSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_AUTH_LIMIT_", env_file=None, hide_input_in_errors=True
    )
    enabled: bool = False
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=6379, ge=1, le=65535)
    password: SecretStr | None = None
    timeout_seconds: float = Field(default=0.2, ge=0.05, le=1)
    login_limit: int = Field(default=5, ge=1, le=10000)
    login_window_seconds: int = Field(default=60, ge=1, le=86400)
    register_limit: int = Field(default=3, ge=1, le=10000)
    register_window_seconds: int = Field(default=600, ge=1, le=86400)


def create_auth_limiter(settings: AuthLimitSettings, environment: str):
    client = Redis(
        host=settings.host,
        port=settings.port,
        password=settings.password.get_secret_value() if settings.password else None,
        socket_connect_timeout=settings.timeout_seconds,
        socket_timeout=settings.timeout_seconds,
        retry=Retry(NoBackoff(), 0),
        max_connections=10,
    )
    return AuthLimiter(client, settings, environment)


class AuthLimiter:
    def __init__(self, client, settings: AuthLimitSettings, environment: str):
        self.client = client
        self.settings = settings
        self.environment = environment

    def key(self, operation: Operation, host: str) -> str:
        address = ip_address(host)
        if address.version == 6 and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        # Pseudonymous key component, NOT anonymization of the small IP space.
        identity = sha256(address.compressed.encode("ascii")).hexdigest()
        return f"opsdesk:{self.environment}:auth-limit:v1:{operation}:ip:{identity}"

    def check(self, operation: Operation, host: str | None) -> None:
        if operation not in ("login", "register"):
            raise ValueError("Unknown limiter operation")
        limit = getattr(self.settings, f"{operation}_limit")
        window_ms = getattr(self.settings, f"{operation}_window_seconds") * 1000
        try:
            if host is None:
                raise ValueError("Client address missing")
            key = self.key(operation, host)
            result = self.client.eval(SCRIPT, 1, key, limit, window_ms)
            if (
                not isinstance(result, (list, tuple))
                or len(result) != 3
                or any(type(value) is not int for value in result)
            ):
                raise ValueError("Invalid limiter reply")
            allowed, used, ttl = result
            if (
                allowed not in (0, 1)
                or not 1 <= used <= limit
                or not 0 <= ttl <= window_ms
                or (allowed == 0 and used != limit)
            ):
                raise ValueError("Inconsistent limiter reply")
        except RedisError, ValueError, TypeError:
            logger.warning("auth_limit_unavailable")
            raise ApiError("service_unavailable") from None
        if not allowed:
            logger.info("auth_limit_rejected")
            raise ApiError("rate_limited", retry_after=max(1, ceil(ttl / 1000)))

    def close(self):
        self.client.close()


def enforce_auth_limit(request: Request, operation: Operation) -> None:
    limiter = request.app.state.auth_limiter
    if limiter is not None:
        # ASGI client is resolved by the server's trusted-proxy policy, not headers here.
        limiter.check(operation, request.client.host if request.client else None)
