"""Explicit, guarded migrations inside Railway's private network."""

import re

from pydantic_settings import SettingsConfigDict
from sqlalchemy import URL, Connection, Engine, create_engine, text
from sqlalchemy.pool import NullPool

from opsdesk.db.config import DatabaseSettings


class HostedMigrationSettings(DatabaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_MIGRATION_",
        env_file=None,
        hide_input_in_errors=True,
        frozen=True,
    )


def validate_hosted_migration_target(
    settings: HostedMigrationSettings,
) -> None:
    private_host = re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.railway\.internal",
        settings.host,
    )

    if (
        private_host is None
        or settings.port != 5432
        or settings.database != "opsdesk_demo"
        or settings.username != "opsdesk_migrator"
    ):
        raise ValueError("Unsafe hosted migration target.")


def create_hosted_migration_engine(
    settings: HostedMigrationSettings,
) -> Engine:
    validate_hosted_migration_target(settings)

    url = URL.create(
        "postgresql+psycopg",
        username=settings.username,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )

    return create_engine(
        url,
        echo=False,
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": 10,
            "sslmode": "require",
        },
    )


def verify_hosted_connection(connection: Connection) -> None:
    """Check the connected identity inside the migration transaction."""
    identity = connection.execute(
        text(
            """
            SELECT
                current_database(),
                current_user,
                inet_server_port(),
                rolsuper,
                rolcreatedb,
                rolcreaterole,
                rolreplication,
                rolbypassrls
            FROM pg_catalog.pg_roles
            WHERE rolname = current_user
            """
        )
    ).one()

    if tuple(identity) != (
        "opsdesk_demo",
        "opsdesk_migrator",
        5432,
        False,
        False,
        False,
        False,
        False,
    ):
        raise ValueError("Unexpected hosted migration connection.")

    connection.exec_driver_sql("SET LOCAL search_path TO public")
