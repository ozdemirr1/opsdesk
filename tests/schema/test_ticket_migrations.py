import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import create_integration_engine

IDENTITY_REVISION = "6a3066cd5538"
HEAD_REVISION = "31be9023cfb2"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPSDESK_RUN_SCHEMA_TESTS") != "1",
        reason=("Schema-changing tests require OPSDESK_RUN_SCHEMA_TESTS=1."),
    ),
]


def read_identity_rows(connection):
    user = connection.execute(
        text("SELECT user_id, email, password_hash, is_active FROM public.users")
    ).one()
    organization = connection.execute(
        text("SELECT organization_id, name, is_active FROM public.organizations")
    ).one()
    membership = connection.execute(
        text(
            "SELECT membership_id, user_id, "
            "organization_id, role, is_active "
            "FROM public.organization_memberships"
        )
    ).one()

    return (
        tuple(user),
        tuple(organization),
        tuple(membership),
    )


def assert_head_schema(engine) -> None:
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        tables = set(
            inspect(connection).get_table_names(
                schema="public",
            )
        )

        assert revision == HEAD_REVISION
        assert "tickets" in tables


def clean_product_rows(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM public.tickets"))
        connection.execute(text("DELETE FROM public.organization_memberships"))
        connection.execute(text("DELETE FROM public.users"))
        connection.execute(text("DELETE FROM public.organizations"))


def test_ticket_migration_cycle_preserves_identity_records(
    request,
):
    settings = IntegrationDatabaseSettings()
    engine = create_integration_engine(settings)

    config = Config()
    migrations = Path(__file__).resolve().parents[2] / "migrations"
    config.set_main_option(
        "script_location",
        str(migrations),
    )

    body_error = None

    try:
        with engine.connect() as connection:
            target = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "host(inet_server_addr()), "
                    "inet_server_port()"
                )
            ).one()

            assert tuple(target) == (
                "opsdesk_product_test",
                "opsdesk_product_test_runner",
                "127.0.0.1",
                5432,
            )

        assert_head_schema(engine)
        clean_product_rows(engine)

        with engine.begin() as connection:
            user_id = connection.execute(
                text(
                    "INSERT INTO public.users "
                    "(email, password_hash) "
                    "VALUES (:email, :password_hash) "
                    "RETURNING user_id"
                ),
                {
                    "email": "migration-ticket@example.com",
                    "password_hash": ("test-only-hash-placeholder"),
                },
            ).scalar_one()

            organization_id = connection.execute(
                text(
                    "INSERT INTO public.organizations "
                    "(name) VALUES (:name) "
                    "RETURNING organization_id"
                ),
                {
                    "name": "Migration Preservation",
                },
            ).scalar_one()

            connection.execute(
                text(
                    "INSERT INTO "
                    "public.organization_memberships "
                    "(user_id, organization_id, role) "
                    "VALUES "
                    "(:user_id, :organization_id, 'owner') "
                    "RETURNING membership_id"
                ),
                {
                    "user_id": user_id,
                    "organization_id": organization_id,
                },
            ).scalar_one()

        with engine.connect() as connection:
            expected_identity = read_identity_rows(connection)

        command.downgrade(config, IDENTITY_REVISION)

        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one()
            tables = set(
                inspect(connection).get_table_names(
                    schema="public",
                )
            )

            assert revision == IDENTITY_REVISION
            assert "tickets" not in tables
            assert read_identity_rows(connection) == expected_identity

        command.upgrade(config, HEAD_REVISION)
        assert_head_schema(engine)

        with engine.connect() as connection:
            assert read_identity_rows(connection) == expected_identity
            ticket_count = connection.execute(
                text("SELECT COUNT(*) FROM public.tickets")
            ).scalar_one()
            assert ticket_count == 0

    except Exception as exc:
        body_error = exc
        raise

    finally:
        try:
            command.upgrade(config, HEAD_REVISION)
            assert_head_schema(engine)
            clean_product_rows(engine)
        except Exception as restore_error:
            request.session.shouldstop = (
                "Ticket migration restoration failed; stopping test execution."
            )

            if body_error is not None:
                raise ExceptionGroup(
                    "Ticket migration test and restoration failed.",
                    [body_error, restore_error],
                ) from None

            raise
        finally:
            engine.dispose()
