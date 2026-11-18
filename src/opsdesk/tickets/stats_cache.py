"""Optional, bounded Redis cache for authorized Ticket counts."""

import logging

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from opsdesk.tickets.read_models import TicketStats
from opsdesk.tickets.read_schemas import TicketStatsResponse

logger = logging.getLogger("opsdesk.cache")


class StatsCacheSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_STATS_CACHE_", env_file=None, hide_input_in_errors=True
    )
    enabled: bool = False
    host: str = Field(default="127.0.0.1", min_length=1)
    port: int = Field(default=6379, ge=1, le=65535)
    password: SecretStr | None = None
    ttl_seconds: int = Field(default=30, ge=1, le=300)
    timeout_seconds: float = Field(default=0.2, ge=0.05, le=1)


def create_cache(settings: StatsCacheSettings, environment: str):
    client = Redis(
        host=settings.host,
        port=settings.port,
        password=settings.password.get_secret_value() if settings.password else None,
        socket_connect_timeout=settings.timeout_seconds,
        socket_timeout=settings.timeout_seconds,
        retry=Retry(NoBackoff(), 0),
        max_connections=10,
        decode_responses=False,
    )
    return TicketStatsCache(client, environment, settings.ttl_seconds)


class TicketStatsCache:
    def __init__(self, client, environment: str, ttl_seconds: int):
        self.client = client
        self.environment = environment
        self.ttl_seconds = ttl_seconds

    def key(self, actor_user_id: int, organization_id: int, scope: tuple[int, str]):
        membership_id, role = scope
        visibility = "own" if role == "customer" else "all"
        return (
            f"opsdesk:{self.environment}:ticket-stats:v1:org:{organization_id}:"
            f"user:{actor_user_id}:membership:{membership_id}:scope:{visibility}"
        )

    def get(self, key: str) -> tuple[TicketStats | None, bool]:
        try:
            raw = self.client.get(key)
        except RedisError:
            logger.warning("ticket_stats_cache_read_unavailable")
            return None, False
        if raw is None:
            logger.info("ticket_stats_cache_miss")
            return None, True
        try:
            if len(raw) > 4096:
                raise ValueError("Oversized cache value")
            parsed = TicketStatsResponse.model_validate_json(raw)
            counts = parsed.by_status.model_dump()
            if parsed.total != sum(counts.values()):
                raise ValueError("Inconsistent total")
        except ValidationError, ValueError, TypeError:
            logger.warning("ticket_stats_cache_invalid_value")
            return None, True
        logger.info("ticket_stats_cache_hit")
        return TicketStats(parsed.total, counts), True

    def put(self, key: str, stats: TicketStats) -> None:
        payload = TicketStatsResponse.model_validate(stats).model_dump_json()
        try:
            self.client.set(key, payload, ex=self.ttl_seconds)
        except RedisError:
            logger.warning("ticket_stats_cache_write_unavailable")

    def close(self):
        self.client.close()
