import os
import runpy
import traceback
from pathlib import Path
from unittest.mock import MagicMock, Mock

import alembic
import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import Connection
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool

from opsdesk.db import compose
from opsdesk.db.compose import (
    ComposeMigrationSettings,
    create_compose_migration_engine,
    validate_compose_migration_target,
    verify_compose_connection,
)

SYNTHETIC_SETTINGS = {
    "HOST": "db",
    "PORT": "5432",
    "DATABASE": "opsdesk_compose_dev",
    "USERNAME": "opsdesk_compose_migrator",
    "PASSWORD": "synthetic-migration-password",
}


@pytest.fixture(autouse=True)
def isolate_database_environment(monkeypatch: pytest.MonkeyPatch):
    # Tests must not depend on the developer's real database settings.
    for name in tuple(os.environ):
        if name.startswith(("OPSDESK_DB_", "OPSDESK_COMPOSE_MIGRATION_")):
            monkeypatch.delenv(name)


def set_environment(
    monkeypatch: pytest.MonkeyPatch,
    prefix: str = "OPSDESK_COMPOSE_MIGRATION_",
) -> None:
    for name, value in SYNTHETIC_SETTINGS.items():
        monkeypatch.setenv(f"{prefix}{name}", value)


def test_reads_migration_environment(monkeypatch: pytest.MonkeyPatch):
    set_environment(monkeypatch)

    settings = ComposeMigrationSettings()

    assert settings.host == "db"
    assert settings.port == 5432
    assert settings.database == "opsdesk_compose_dev"
    assert settings.username == "opsdesk_compose_migrator"
    assert settings.password.get_secret_value() == SYNTHETIC_SETTINGS["PASSWORD"]


def test_application_environment_is_not_used(
    monkeypatch: pytest.MonkeyPatch,
):
    set_environment(monkeypatch, prefix="OPSDESK_DB_")

    with pytest.raises(ValidationError) as caught:
        ComposeMigrationSettings()

    errors = caught.value.errors(include_input=False)
    missing_fields = {error["loc"][0] for error in errors if error["type"] == "missing"}

    assert missing_fields == {
        "host",
        "port",
        "database",
        "username",
        "password",
    }


def test_password_is_required(monkeypatch: pytest.MonkeyPatch):
    set_environment(monkeypatch)
    monkeypatch.delenv("OPSDESK_COMPOSE_MIGRATION_PASSWORD")

    with pytest.raises(ValidationError) as caught:
        ComposeMigrationSettings()

    errors = caught.value.errors(include_input=False)
    assert any(
        error["loc"] == ("password",) and error["type"] == "missing" for error in errors
    )


@pytest.mark.parametrize("port", ["0", "65536", "not-a-number"])
def test_invalid_port_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    port: str,
):
    set_environment(monkeypatch)
    monkeypatch.setenv("OPSDESK_COMPOSE_MIGRATION_PORT", port)

    with pytest.raises(ValidationError) as caught:
        ComposeMigrationSettings()

    errors = caught.value.errors(include_input=False)
    assert any(error["loc"] == ("port",) for error in errors)


def test_password_is_hidden_in_repr(monkeypatch: pytest.MonkeyPatch):
    set_environment(monkeypatch)

    settings = ComposeMigrationSettings()

    assert SYNTHETIC_SETTINGS["PASSWORD"] not in repr(settings)


def test_expected_migration_target_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
):
    set_environment(monkeypatch)

    settings = ComposeMigrationSettings()

    validate_compose_migration_target(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("DATABASE", "opsdesk_demo"),
        ("DATABASE", "opsdesk_product_dev"),
        ("DATABASE", "opsdesk_product_test"),
        ("USERNAME", "postgres"),
        ("USERNAME", "opsdesk_app"),
    ],
)
def test_unexpected_migration_target_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
):
    set_environment(monkeypatch)
    monkeypatch.setenv(f"OPSDESK_COMPOSE_MIGRATION_{field}", value)

    settings = ComposeMigrationSettings()

    with pytest.raises(
        ValueError,
        match=r"^Unsafe compose migration target\.$",
    ):
        validate_compose_migration_target(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("HOST", "127.0.0.1"),
        ("HOST", "localhost"),
        ("HOST", "postgres.railway.internal"),
        ("HOST", "database.example.com"),
        ("HOST", "db.example.com"),
        ("HOST", "db,localhost"),
        ("PORT", "5433"),
    ],
)
def test_unsafe_address_is_rejected_before_engine_creation(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
):
    set_environment(monkeypatch)
    monkeypatch.setenv(f"OPSDESK_COMPOSE_MIGRATION_{field}", value)
    factory = Mock()
    monkeypatch.setattr(compose, "create_engine", factory)

    with pytest.raises(ValueError, match="Unsafe compose migration target"):
        create_compose_migration_engine(ComposeMigrationSettings())

    factory.assert_not_called()


def test_engine_uses_migration_credentials_and_connection_options(
    monkeypatch: pytest.MonkeyPatch,
):
    set_environment(monkeypatch)
    factory = Mock()
    monkeypatch.setattr(compose, "create_engine", factory)

    engine = create_compose_migration_engine(ComposeMigrationSettings())

    assert engine is factory.return_value
    factory.assert_called_once()

    url = factory.call_args.args[0]
    assert url.drivername == "postgresql+psycopg"
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "opsdesk_compose_dev"
    assert url.username == "opsdesk_compose_migrator"
    assert url.password == SYNTHETIC_SETTINGS["PASSWORD"]
    assert SYNTHETIC_SETTINGS["PASSWORD"] not in str(url)

    assert factory.call_args.kwargs == {
        "echo": False,
        "hide_parameters": True,
        "poolclass": NullPool,
        "connect_args": {
            "connect_timeout": 10,
            "sslmode": "disable",
        },
    }


EXPECTED_IDENTITY = (
    "opsdesk_compose_dev",
    "opsdesk_compose_migrator",
    5432,
    False,
    False,
    False,
    False,
    False,
)


def test_expected_connection_sets_transaction_search_path():
    connection = Mock(spec=Connection)
    connection.execute.return_value.one.return_value = EXPECTED_IDENTITY

    verify_compose_connection(connection)

    connection.exec_driver_sql.assert_called_once_with(
        "SET LOCAL search_path TO public"
    )


@pytest.mark.parametrize(
    ("index", "value"),
    [
        (0, "railway"),
        (1, "postgres"),
        (2, 5433),
        (3, True),
        (4, True),
        (5, True),
        (6, True),
        (7, True),
    ],
)
def test_unexpected_connection_is_rejected_before_schema_setup(
    index: int,
    value: object,
):
    identity = list(EXPECTED_IDENTITY)
    identity[index] = value

    connection = Mock(spec=Connection)
    connection.execute.return_value.one.return_value = tuple(identity)

    with pytest.raises(
        ValueError,
        match="Unexpected compose migration connection",
    ):
        verify_compose_connection(connection)

    connection.exec_driver_sql.assert_not_called()


@pytest.mark.parametrize(
    "outcome",
    ["success", "wrong_identity", "ddl_error"],
)
def test_explicit_compose_migration_uses_verified_transaction(
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
):
    set_environment(monkeypatch)

    engine = MagicMock()
    connection_scope = engine.connect.return_value
    connection_scope.__exit__.return_value = False
    connection = connection_scope.__enter__.return_value

    transaction_scope = connection.begin.return_value
    transaction_scope.__exit__.return_value = False

    def read_identity(_statement):
        # Identity verification must happen inside the transaction.
        transaction_scope.__enter__.assert_called_once_with()
        result = Mock()
        result.one.return_value = EXPECTED_IDENTITY
        if outcome == "wrong_identity":
            result.one.return_value = (
                "wrong_database",
                *EXPECTED_IDENTITY[1:],
            )
        return result

    connection.execute.side_effect = read_identity

    factory = Mock(return_value=engine)
    monkeypatch.setattr(compose, "create_compose_migration_engine", factory)

    context = MagicMock()
    context.config = Config()
    context.is_offline_mode.return_value = False
    context.get_x_argument.return_value = {"target": "compose"}
    context.begin_transaction.return_value.__exit__.return_value = False

    def check_verified_connection(**_kwargs):
        connection.exec_driver_sql.assert_called_once_with(
            "SET LOCAL search_path TO public"
        )

    context.configure.side_effect = check_verified_connection
    monkeypatch.setattr(alembic, "context", context)

    env_path = Path(__file__).resolve().parents[1] / "migrations" / "env.py"

    if outcome == "wrong_identity":
        with pytest.raises(
            ValueError,
            match="Unexpected compose migration connection",
        ):
            runpy.run_path(str(env_path))

        context.configure.assert_not_called()
        context.run_migrations.assert_not_called()
        connection.exec_driver_sql.assert_not_called()

    elif outcome == "ddl_error":
        secret_marker = "synthetic-compose-error-secret"
        context.run_migrations.side_effect = OperationalError(
            None,
            None,
            RuntimeError(secret_marker),
        )

        with pytest.raises(
            RuntimeError,
            match=r"^Migration database operation failed\.$",
        ) as caught:
            runpy.run_path(str(env_path))

        rendered = "".join(traceback.format_exception(caught.value))
        assert secret_marker not in rendered

    else:
        runpy.run_path(str(env_path))

        transaction_scope.__exit__.assert_called_once_with(None, None, None)

    factory.assert_called_once()
    configured = factory.call_args.args[0]
    assert isinstance(configured, ComposeMigrationSettings)
    assert configured.database == "opsdesk_compose_dev"
    assert configured.username == "opsdesk_compose_migrator"

    if outcome != "success":
        transaction_scope.__exit__.assert_called_once()
        assert transaction_scope.__exit__.call_args.args[0] is not None

    if outcome != "wrong_identity":
        context.configure.assert_called_once()
        assert context.configure.call_args.kwargs["connection"] is connection
        context.run_migrations.assert_called_once_with()

    connection_scope.__exit__.assert_called_once()
    engine.dispose.assert_called_once_with()
