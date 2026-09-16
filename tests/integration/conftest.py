import os
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.config import IntegrationDatabaseSettings
from opsdesk.db.connection import (
    create_integration_engine,
    verify_database_connection,
)
from opsdesk.db.session import create_session_factory


@contextmanager
def safe_database_errors():
    try:
        yield
    except SQLAlchemyError:
        raise RuntimeError("Database operation failed.") from None


@pytest.fixture
def integration_engine():
    if os.environ.get("OPSDESK_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip(
            "Integration tests are skipped. Set OPSDESK_RUN_INTEGRATION_TESTS=1 to run them."
        )

    settings = IntegrationDatabaseSettings()
    engine = create_integration_engine(settings)

    try:
        verify_database_connection(engine)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def probe_scope(integration_engine, request):
    with safe_database_errors():
        with integration_engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS public.integration_probe ("
                    "    marker TEXT PRIMARY KEY"
                    ")"
                )
            )

    factory = create_session_factory(integration_engine)

    def clean_probe():
        try:
            with safe_database_errors():
                with integration_engine.begin() as connection:
                    connection.execute(text("DELETE FROM public.integration_probe"))
        except Exception:
            request.session.shouldstop = (
                "Probe cleanup failed; stopping to preserve test isolation."
            )
            raise

    @contextmanager
    def isolated_scope():
        clean_probe()
        body_error = None

        try:
            with safe_database_errors():
                yield factory
        except Exception as exc:
            body_error = exc
            raise
        finally:
            try:
                clean_probe()
            except Exception as cleanup_error:
                if body_error is not None:
                    raise ExceptionGroup(
                        "Probe body and cleanup failed.",
                        [body_error, cleanup_error],
                    ) from None
                raise

    return isolated_scope
