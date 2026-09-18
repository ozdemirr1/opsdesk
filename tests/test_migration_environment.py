import runpy
import traceback
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock

import alembic
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import OperationalError

import opsdesk.db.config
import opsdesk.db.connection


@pytest.mark.parametrize(
    ("host", "port", "database"),
    [
        ("127.0.0.1", "5432", "opsdesk_product_dev"),
        ("127.0.0.1", "5432", "opsdesk_dev"),
        ("127.0.0.1", "5432", "opsdesk_test"),
        ("localhost", "5432", "opsdesk_product_test"),
        ("127.0.0.1", "5433", "opsdesk_product_test"),
        ("127.0.0.1", "5432", "another_test"),
        ("127.0.0.1", "5432", "opsdesk_product_test "),
    ],
)
def test_migrations_reject_unsafe_target_before_engine_creation(
    monkeypatch, host, port, database
):
    settings = {
        "HOST": host,
        "PORT": port,
        "DATABASE": database,
        "USERNAME": "opsdesk_product_test_runner",
        "PASSWORD": "synthetic-test-password",
    }
    for key, value in settings.items():
        monkeypatch.setenv(f"OPSDESK_TEST_DB_{key}", value)

    engine_factory = Mock(
        side_effect=AssertionError("Engine creation must not be reached.")
    )
    monkeypatch.setattr(
        opsdesk.db.connection,
        "create_database_engine",
        engine_factory,
    )

    config = Config()
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    config.set_main_option("script_location", str(migrations_dir))

    with pytest.raises(
        ValueError,
        match=r"^Unsafe integration-test database target\.$",
    ):
        command.current(config)

    engine_factory.assert_not_called()


def test_migrations_dispose_engine_and_hide_connection_error(
    monkeypatch, caplog, capsys
):
    synthetic_password = "migration-secret-marker"
    synthetic_url = (
        f"postgresql+psycopg://test_user:{synthetic_password}"
        "@127.0.0.1:5432/opsdesk_product_test"
    )

    settings = {
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "DATABASE": "opsdesk_product_test",
        "USERNAME": "opsdesk_product_test_runner",
        "PASSWORD": synthetic_password,
    }
    for key, value in settings.items():
        monkeypatch.setenv(f"OPSDESK_TEST_DB_{key}", value)

    original_error = OperationalError(
        None,
        None,
        RuntimeError(f"{synthetic_password} {synthetic_url}"),
    )
    engine = Mock()
    engine.connect.side_effect = original_error
    engine_factory = Mock(return_value=engine)
    monkeypatch.setattr(
        opsdesk.db.connection,
        "create_database_engine",
        engine_factory,
    )

    config = Config()
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    config.set_main_option("script_location", str(migrations_dir))

    with pytest.raises(
        RuntimeError,
        match=r"^Migration database operation failed\.$",
    ) as exc_info:
        command.current(config)

    engine_factory.assert_called_once()
    engine.connect.assert_called_once_with()
    engine.dispose.assert_called_once_with()

    rendered = "".join(traceback.format_exception(exc_info.value))
    captured = capsys.readouterr()
    visible_output = rendered + captured.out + captured.err + caplog.text

    assert synthetic_password not in visible_output
    assert synthetic_url not in visible_output


@pytest.mark.parametrize("migration_fails", [False, True])
def test_migrations_release_resources_after_connection(monkeypatch, migration_fails):
    settings = {
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "DATABASE": "opsdesk_product_test",
        "USERNAME": "opsdesk_product_test_runner",
        "PASSWORD": "synthetic-test-password",
    }
    for key, value in settings.items():
        monkeypatch.setenv(f"OPSDESK_TEST_DB_{key}", value)

    engine = MagicMock()
    connection_scope = engine.connect.return_value
    connection_scope.__exit__.return_value = False
    connection = connection_scope.__enter__.return_value

    monkeypatch.setattr(
        opsdesk.db.connection,
        "create_database_engine",
        Mock(return_value=engine),
    )

    migration_context = MagicMock()
    migration_context.config = Config()
    migration_context.is_offline_mode.return_value = False
    transaction_scope = migration_context.begin_transaction.return_value
    transaction_scope.__exit__.return_value = False

    if migration_fails:
        migration_context.run_migrations.side_effect = OperationalError(
            None, None, RuntimeError("synthetic migration failure")
        )

    monkeypatch.setattr(alembic, "context", migration_context)
    env_path = Path(__file__).resolve().parents[1] / "migrations" / "env.py"

    if migration_fails:
        with pytest.raises(
            RuntimeError,
            match=r"^Migration database operation failed\.$",
        ):
            runpy.run_path(str(env_path))
    else:
        runpy.run_path(str(env_path))

    engine.connect.assert_called_once_with()
    connection_scope.__enter__.assert_called_once_with()

    name_filter = migration_context.configure.call_args.kwargs["include_name"]

    assert name_filter("integration_probe", "table", {}) is False
    assert name_filter("integration_probe", "column", {}) is True

    for table_name in ("users", "organizations", "organization_memberships"):
        assert name_filter(table_name, "table", {}) is True

    assert name_filter("another_table", "table", {}) is True

    migration_context.configure.assert_called_once()
    assert migration_context.configure.call_args.kwargs["connection"] is connection
    migration_context.begin_transaction.assert_called_once_with()
    transaction_scope.__enter__.assert_called_once_with()
    migration_context.run_migrations.assert_called_once_with()
    transaction_scope.__exit__.assert_called_once()
    connection_scope.__exit__.assert_called_once()
    engine.dispose.assert_called_once_with()


def test_offline_migrations_generate_sql_without_database_settings(monkeypatch):
    settings_factory = Mock(
        side_effect=AssertionError("Offline mode must not read database settings.")
    )
    engine_factory = Mock(
        side_effect=AssertionError("Offline mode must not create an engine.")
    )

    monkeypatch.setattr(
        opsdesk.db.config,
        "IntegrationDatabaseSettings",
        settings_factory,
    )
    monkeypatch.setattr(
        opsdesk.db.connection,
        "create_integration_engine",
        engine_factory,
    )

    output = StringIO()
    config = Config(output_buffer=output)
    migrations_dir = Path(__file__).resolve().parents[1] / "migrations"
    config.set_main_option("script_location", str(migrations_dir))

    command.upgrade(config, "head", sql=True)

    generated_sql = output.getvalue()
    assert "BEGIN;" in generated_sql
    assert "COMMIT;" in generated_sql
    settings_factory.assert_not_called()
    engine_factory.assert_not_called()
