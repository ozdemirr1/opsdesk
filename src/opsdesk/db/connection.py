from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.config import DatabaseSettings, IntegrationDatabaseSettings
from opsdesk.db.guards import validate_test_target


class DatabaseConnectionError(RuntimeError):
    pass


def build_database_url(settings: DatabaseSettings) -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.username,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )


def create_database_engine(settings: DatabaseSettings) -> Engine:
    url = build_database_url(settings)
    return create_engine(
        url,
        echo=False,
        hide_parameters=True,
    )


def create_integration_engine(settings: IntegrationDatabaseSettings) -> Engine:
    validate_test_target(
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )
    return create_database_engine(settings)


def verify_database_connection(engine: Engine) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise DatabaseConnectionError("Database connection failed.") from None
