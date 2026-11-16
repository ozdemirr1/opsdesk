"""Explicit, guarded migrations inside the isolated local Compose network."""

from pydantic_settings import SettingsConfigDict
from sqlalchemy import URL, Connection, Engine, create_engine, text
from sqlalchemy.pool import NullPool

from opsdesk.db.config import DatabaseSettings


class ComposeMigrationSettings(DatabaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_COMPOSE_MIGRATION_",
        env_file=None,
        hide_input_in_errors=True,
        frozen=True,
    )


def validate_compose_migration_target(
    settings: ComposeMigrationSettings,
) -> None:
    if (
        settings.host != "db"
        or settings.port != 5432
        or settings.database != "opsdesk_compose_dev"
        or settings.username != "opsdesk_compose_migrator"
    ):
        raise ValueError("Unsafe compose migration target.")


def create_compose_migration_engine(
    settings: ComposeMigrationSettings,
) -> Engine:
    validate_compose_migration_target(settings)

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
            "sslmode": "disable",
        },
    )


def verify_compose_connection(connection: Connection) -> None:
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
        "opsdesk_compose_dev",
        "opsdesk_compose_migrator",
        5432,
        False,
        False,
        False,
        False,
        False,
    ):
        raise ValueError("Unexpected compose migration connection.")

    connection.exec_driver_sql("SET LOCAL search_path TO public")
