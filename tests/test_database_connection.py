from unittest.mock import Mock

import pytest

import opsdesk.db.connection
from opsdesk.db.config import DatabaseSettings, IntegrationDatabaseSettings
from opsdesk.db.connection import (
    build_database_url,
    create_database_engine,
    create_integration_engine,
)


def test_build_database_url_preserves_fields_and_special_characters():
    synthetic_password = "my@secret/password%with#symbols"
    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password=synthetic_password,
    )

    url = build_database_url(settings)

    assert url.drivername == "postgresql+psycopg"
    assert url.username == "dev_user"
    assert url.host == "127.0.0.1"
    assert url.port == 5432
    assert url.database == "opsdesk_product_dev"
    assert url.password == synthetic_password


def test_database_url_repr_masks_password():
    synthetic_password = "super-secret-password-to-hide"
    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password=synthetic_password,
    )

    url = build_database_url(settings)

    repr_str = repr(url)
    assert synthetic_password not in repr_str


def test_create_database_engine_passes_url_and_options(monkeypatch):
    mock_create_engine = Mock()
    monkeypatch.setattr(opsdesk.db.connection, "create_engine", mock_create_engine)

    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password="dev_password",
    )

    engine = create_database_engine(settings)

    mock_create_engine.assert_called_once()
    call_args, call_kwargs = mock_create_engine.call_args

    url = call_args[0]
    assert url.drivername == "postgresql+psycopg"
    assert url.database == "opsdesk_product_dev"

    assert call_kwargs == {"echo": False, "hide_parameters": True}
    assert engine is mock_create_engine.return_value


@pytest.mark.parametrize(
    ("host", "port", "database"),
    [
        ("127.0.0.1", 5432, "opsdesk_product_dev"),
        ("localhost", 5432, "opsdesk_product_test"),
        ("127.0.0.1", 5433, "opsdesk_product_test"),
        ("127.0.0.1", 5432, "opsdesk_dev"),
        ("127.0.0.1", 5432, "opsdesk_test"),
    ],
)
def test_create_integration_engine_rejects_invalid_target_and_does_not_create(
    monkeypatch, host, port, database
):
    mock_create_database_engine = Mock()
    monkeypatch.setattr(
        opsdesk.db.connection, "create_database_engine", mock_create_database_engine
    )

    settings = IntegrationDatabaseSettings(
        host=host,
        port=port,
        database=database,
        username="test_user",
        password="test_password",
    )

    with pytest.raises(
        ValueError,
        match=r"^Unsafe integration-test database target\.$",
    ):
        create_integration_engine(settings)

    mock_create_database_engine.assert_not_called()


def test_create_integration_engine_accepts_valid_target_and_creates(monkeypatch):
    mock_create_database_engine = Mock()
    monkeypatch.setattr(
        opsdesk.db.connection, "create_database_engine", mock_create_database_engine
    )

    settings = IntegrationDatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_test",
        username="test_user",
        password="test_password",
    )

    engine = create_integration_engine(settings)

    mock_create_database_engine.assert_called_once_with(settings)
    assert engine is mock_create_database_engine.return_value
