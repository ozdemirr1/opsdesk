"""Verify the exact test target before migration or destructive suites."""

import os
import sys

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import create_integration_engine


def main():
    suite = sys.argv[1]
    if suite not in {"schema", "data"}:
        raise SystemExit("Expected schema or data suite.")
    settings = IntegrationDatabaseSettings()
    if settings.username != "opsdesk_product_test_runner":
        raise SystemExit("Unexpected test role.")
    engine = create_integration_engine(settings)
    try:
        with engine.connect() as connection:
            target = tuple(
                connection.execute(
                    text(
                        "SELECT current_database(), current_user, "
                        "host(inet_server_addr()), inet_server_port()"
                    )
                ).one()
            )
            if target != (
                "opsdesk_product_test",
                "opsdesk_product_test_runner",
                "127.0.0.1",
                5432,
            ):
                raise SystemExit("Unexpected connected test target.")
            privileges = tuple(
                connection.execute(
                    text(
                        "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                ).one()
            )
            if any(privileges):
                raise SystemExit("Test role must not have administrative privileges.")
    except SQLAlchemyError:
        raise SystemExit(
            "CI database verification failed; connection details withheld."
        ) from None
    finally:
        engine.dispose()
    print(
        "Verified exact database, loopback address and restricted test role.",
        flush=True,
    )
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    if suite == "schema":
        os.environ["OPSDESK_RUN_SCHEMA_TESTS"] = "1"
        result = pytest.main(["-q", "tests/schema", "-p", "no:cacheprovider"])
    else:
        os.environ["OPSDESK_RUN_INTEGRATION_TESTS"] = "1"
        result = pytest.main(["-q", "tests/integration", "-p", "no:cacheprovider"])
    if result:
        raise SystemExit(result)
    command.check(config)


if __name__ == "__main__":
    main()
