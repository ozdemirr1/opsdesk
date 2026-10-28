import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import create_integration_engine

HEAD = "84c2f9a17d60"
PREDECESSOR = "31be9023cfb2"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPSDESK_RUN_SCHEMA_TESTS") != "1",
        reason="Requires OPSDESK_RUN_SCHEMA_TESTS=1.",
    ),
]


def ticket_snapshot(connection):
    return tuple(
        connection.execute(
            text("SELECT * FROM public.tickets ORDER BY ticket_id")
        ).all()
    )


@pytest.mark.parametrize("injected_failure", [False, True])
def test_comment_migration_predecessor_cycle_preserves_existing_ticket(
    request, injected_failure
):
    engine = create_integration_engine(IntegrationDatabaseSettings())
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    body_error = None
    before = None
    # Preconditions must pass before entering the destructive/restore block.
    try:
        with engine.connect() as c:
            assert tuple(
                c.execute(
                    text(
                        "SELECT current_database(), current_user, host(inet_server_addr()), inet_server_port()"
                    )
                ).one()
            ) == (
                "opsdesk_product_test",
                "opsdesk_product_test_runner",
                "127.0.0.1",
                5432,
            )
            assert (
                c.execute(
                    text("SELECT version_num FROM public.alembic_version")
                ).scalar_one()
                == HEAD
            )
            assert set(inspect(c).get_table_names()) <= {
                "alembic_version",
                "integration_probe",
                "users",
                "organizations",
                "organization_memberships",
                "tickets",
                "comments",
            }
            for table in (
                "comments",
                "tickets",
                "organization_memberships",
                "organizations",
                "users",
            ):
                assert (
                    c.execute(text(f"SELECT COUNT(*) FROM public.{table}")).scalar_one()
                    == 0
                )
        try:
            command.downgrade(config, PREDECESSOR)
            with engine.begin() as c:
                assert "comments" not in inspect(c).get_table_names()
                u = c.execute(
                    text(
                        "INSERT INTO users(email,password_hash) VALUES ('comment-migration@example.com','synthetic-hash') RETURNING user_id"
                    )
                ).scalar_one()
                o = c.execute(
                    text(
                        "INSERT INTO organizations(name) VALUES ('Comment migration') RETURNING organization_id"
                    )
                ).scalar_one()
                m = c.execute(
                    text(
                        "INSERT INTO organization_memberships(user_id,organization_id,role) VALUES (:u,:o,'owner') RETURNING membership_id"
                    ),
                    {"u": u, "o": o},
                ).scalar_one()
                t = c.execute(
                    text(
                        "INSERT INTO tickets(organization_id,requester_membership_id,creator_membership_id,title,description) VALUES (:o,:m,:m,'Preserve me','Historical description') RETURNING ticket_id"
                    ),
                    {"o": o, "m": m},
                ).scalar_one()
                before = ticket_snapshot(c)
            command.upgrade(config, HEAD)
            with engine.begin() as c:
                assert ticket_snapshot(c) == before
                c.execute(
                    text(
                        "INSERT INTO comments(organization_id,ticket_id,author_membership_id,content) VALUES (:o,:t,:m,:content)"
                    ),
                    {"o": o, "t": t, "m": m, "content": "Migration test comment"},
                )
            command.downgrade(config, PREDECESSOR)
            with engine.connect() as c:
                assert ticket_snapshot(c) == before
                assert "comments" not in inspect(c).get_table_names()
            if injected_failure:
                # Exercise the restoration path without leaving the test DB downgraded.
                raise RuntimeError("Synthetic comment migration failure")
        except RuntimeError as error:
            if (
                not injected_failure
                or str(error) != "Synthetic comment migration failure"
            ):
                body_error = error
                raise
        except Exception as error:
            body_error = error
            raise
        finally:
            try:
                command.upgrade(config, HEAD)
                with engine.begin() as c:
                    assert (
                        c.execute(
                            text("SELECT version_num FROM alembic_version")
                        ).scalar_one()
                        == HEAD
                    )
                    if before is not None:
                        assert ticket_snapshot(c) == before
                    assert (
                        c.execute(text("SELECT COUNT(*) FROM comments")).scalar_one()
                        == 0
                    )
                    for table in (
                        "comments",
                        "tickets",
                        "organization_memberships",
                        "users",
                        "organizations",
                    ):
                        c.execute(text(f"DELETE FROM public.{table}"))
                command.check(config)
            except Exception as restoration:
                request.session.shouldstop = (
                    "Comment schema restoration failed; stopping test execution."
                )
                if body_error:
                    raise ExceptionGroup(
                        "Comment migration and restoration failed",
                        [body_error, restoration],
                    ) from None
                raise
    finally:
        engine.dispose()
