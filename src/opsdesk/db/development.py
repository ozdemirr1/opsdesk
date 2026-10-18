"""Explicit, guarded local development migration target."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL, Connection, Engine, create_engine, text


class DevelopmentMigrationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_DB_",
        env_file=None,
        hide_input_in_errors=True,
        frozen=True,
    )

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)
    # Omission delegates authentication to libpq; server rules still apply.
    # Application DatabaseSettings continues to require an explicit password.
    password: SecretStr | None = Field(default=None, min_length=1)


def create_development_migration_engine(
    settings: DevelopmentMigrationSettings,
) -> Engine:
    if (settings.host, settings.port, settings.database, settings.username) != (
        "127.0.0.1",
        5432,
        "opsdesk_product_dev",
        "opsdesk_product_app",
    ):
        raise ValueError("Unsafe development migration target.")
    url = URL.create(
        "postgresql+psycopg",
        username=settings.username,
        password=settings.password.get_secret_value() if settings.password else None,
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )
    return create_engine(url, echo=False, hide_parameters=True)


def verify_development_connection(connection: Connection) -> None:
    identity = connection.execute(
        text(
            "SELECT current_database(), current_user, "
            "host(inet_server_addr()), inet_server_port()"
        )
    ).one()
    if tuple(identity) != (
        "opsdesk_product_dev",
        "opsdesk_product_app",
        "127.0.0.1",
        5432,
    ):
        raise ValueError("Unexpected development migration connection.")
    connection.exec_driver_sql("SET LOCAL search_path TO public")
