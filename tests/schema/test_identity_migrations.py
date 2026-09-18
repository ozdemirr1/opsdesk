import os
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import create_integration_engine

REVISION = "6a3066cd5538"
IDENTITY_TABLES = {"users", "organizations", "organization_memberships"}

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPSDESK_RUN_SCHEMA_TESTS") != "1",
        reason="Schema-changing tests require OPSDESK_RUN_SCHEMA_TESTS=1.",
    ),
]


class InjectedMigrationTestFailure(RuntimeError):
    pass


@contextmanager
def safe_schema_errors():
    try:
        yield
    except SQLAlchemyError:
        raise RuntimeError("Schema database operation failed.") from None


def assert_expected_schema(engine):
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        assert revision == REVISION

        tables = set(inspect(connection).get_table_names(schema="public"))
        assert IDENTITY_TABLES.issubset(tables)


@pytest.mark.parametrize("body_fails", [False, True])
def test_identity_migration_cycle_restores_schema(request, body_fails):
    settings = IntegrationDatabaseSettings()
    engine = create_integration_engine(settings)

    config = Config()
    migrations = Path(__file__).resolve().parents[2] / "migrations"
    config.set_main_option("script_location", str(migrations))

    try:
        with safe_schema_errors():
            # Preconditions: no schema changes before all checks pass.
            with engine.connect() as connection:
                target = connection.execute(
                    text(
                        "SELECT current_database(), current_user, "
                        "host(inet_server_addr()), inet_server_port()"
                    )
                ).one()
                assert tuple(target) == (
                    "opsdesk_product_test",
                    "opsdesk_product_test_runner",
                    "127.0.0.1",
                    5432,
                )

                revision = connection.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalar_one()
                assert revision == REVISION

                counts = connection.execute(
                    text(
                        "SELECT "
                        "(SELECT COUNT(*) FROM public.users), "
                        "(SELECT COUNT(*) FROM public.organizations), "
                        "(SELECT COUNT(*) FROM public.organization_memberships)"
                    )
                ).one()
                assert tuple(counts) == (0, 0, 0), (
                    "Schema tests require empty identity tables."
                )

                original_tables = set(
                    inspect(connection).get_table_names(schema="public")
                )
                assert original_tables <= (
                    IDENTITY_TABLES | {"alembic_version", "integration_probe"}
                ), "Unexpected tables in schema-test database."

            expectation = (
                pytest.raises(
                    InjectedMigrationTestFailure,
                    match="Synthetic failure after downgrade",
                )
                if body_fails
                else nullcontext()
            )

            with expectation:
                body_error = None
                try:
                    command.downgrade(config, "base")

                    with engine.connect() as connection:
                        tables = set(
                            inspect(connection).get_table_names(schema="public")
                        )
                        assert tables == original_tables - IDENTITY_TABLES

                        revisions = connection.execute(
                            text("SELECT version_num FROM public.alembic_version")
                        ).all()
                        assert revisions == []

                    if body_fails:
                        raise InjectedMigrationTestFailure(
                            "Synthetic failure after downgrade"
                        )

                    command.upgrade(config, REVISION)
                    assert_expected_schema(engine)

                except Exception as exc:
                    body_error = exc
                    raise

                finally:
                    try:
                        with safe_schema_errors():
                            command.upgrade(config, REVISION)
                            assert_expected_schema(engine)
                    except Exception as restore_error:
                        request.session.shouldstop = (
                            "Schema restoration failed; stopping test execution."
                        )
                        if body_error is not None:
                            raise ExceptionGroup(
                                "Migration test and schema restoration failed.",
                                [body_error, restore_error],
                            ) from None
                        raise

            assert_expected_schema(engine)

    finally:
        engine.dispose()
