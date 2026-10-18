from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError

import opsdesk.db.development as development


def settings(**overrides):
    return development.DevelopmentMigrationSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="opsdesk_product_app",
        password=None,
    ).model_copy(update=overrides)


@pytest.mark.parametrize(
    "override",
    [
        {"host": "localhost"},
        {"port": 5433},
        {"database": "opsdesk_product_test"},
        {"database": "opsdesk_dev"},
        {"username": "opsdesk_product_test_runner"},
        {"username": "postgres"},
    ],
)
def test_development_guard_rejects_before_connect(monkeypatch, override):
    factory = Mock()
    monkeypatch.setattr(development, "create_engine", factory)
    with pytest.raises(ValueError, match="Unsafe development migration target"):
        development.create_development_migration_engine(settings(**override))
    factory.assert_not_called()


@pytest.mark.parametrize("password", [None, SecretStr("synthetic-only")])
def test_development_url_keeps_authentication_and_logging_options(
    monkeypatch, password
):
    factory = Mock()
    monkeypatch.setattr(development, "create_engine", factory)
    development.create_development_migration_engine(settings(password=password))
    url = factory.call_args.args[0]
    assert url.database == "opsdesk_product_dev"
    assert url.username == "opsdesk_product_app"
    assert url.password == (password.get_secret_value() if password else None)
    assert factory.call_args.kwargs == {"echo": False, "hide_parameters": True}
    assert "synthetic-only" not in str(url)


@pytest.mark.parametrize(
    "identity",
    [
        ("opsdesk_product_test", "opsdesk_product_app", "127.0.0.1", 5432),
        ("opsdesk_product_dev", "postgres", "127.0.0.1", 5432),
        ("opsdesk_product_dev", "opsdesk_product_app", "::1", 5432),
        ("opsdesk_product_dev", "opsdesk_product_app", "127.0.0.1", 5433),
    ],
)
def test_actual_connection_must_match_before_schema_selection(identity):
    connection = Mock()
    connection.execute.return_value.one.return_value = identity
    with pytest.raises(ValueError, match="Unexpected development migration connection"):
        development.verify_development_connection(connection)
    connection.exec_driver_sql.assert_not_called()


def migration_config(target):
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )
    config.cmd_opts = Namespace(x=[f"target={target}"])
    return config


def test_unknown_target_is_rejected_before_settings(monkeypatch):
    factory = Mock(side_effect=AssertionError("Must not load settings"))
    monkeypatch.setattr(development, "DevelopmentMigrationSettings", factory)
    with pytest.raises(ValueError, match="Unknown migration target"):
        command.current(migration_config("production"))
    factory.assert_not_called()


@pytest.mark.parametrize("outcome", ["success", "wrong_identity", "ddl_error"])
def test_explicit_development_upgrade_uses_transaction(monkeypatch, outcome):
    # Offline DDL is also exercised by the existing migration environment tests.
    # This checks target wiring and outer transaction ownership without a database.
    import runpy

    import alembic

    configured = settings()
    monkeypatch.setattr(
        development, "DevelopmentMigrationSettings", Mock(return_value=configured)
    )
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.one.return_value = (
        "opsdesk_product_dev",
        "opsdesk_product_app",
        "127.0.0.1",
        5432,
    )
    monkeypatch.setattr(
        development, "create_development_migration_engine", Mock(return_value=engine)
    )
    context = MagicMock()
    context.config = Config()
    context.is_offline_mode.return_value = False
    context.get_x_argument.return_value = {"target": "development"}
    monkeypatch.setattr(alembic, "context", context)
    env_path = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
    if outcome == "wrong_identity":
        connection.execute.return_value.one.return_value = ("wrong", "wrong", None, 0)
        with pytest.raises(
            ValueError, match="Unexpected development migration connection"
        ):
            runpy.run_path(str(env_path))
        context.run_migrations.assert_not_called()
        context.configure.assert_not_called()
    elif outcome == "ddl_error":
        context.run_migrations.side_effect = OperationalError(
            None, None, RuntimeError("synthetic")
        )
        with pytest.raises(RuntimeError, match="Migration database operation failed"):
            runpy.run_path(str(env_path))
    else:
        runpy.run_path(str(env_path))
        connection.begin.return_value.__exit__.assert_called_once_with(None, None, None)
    if outcome != "success":
        assert connection.begin.return_value.__exit__.call_args.args[0] is not None
    engine.dispose.assert_called_once_with()
    if outcome == "wrong_identity":
        connection.exec_driver_sql.assert_not_called()
        return
    connection.exec_driver_sql.assert_called_once_with(
        "SET LOCAL search_path TO public"
    )
    context.run_migrations.assert_called_once_with()
