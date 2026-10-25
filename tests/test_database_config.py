import pytest
from pydantic import ValidationError

from opsdesk.db.config import DatabaseSettings, IntegrationDatabaseSettings


def test_database_settings_accepts_explicit_fields():
    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password="dev_password",
    )

    assert settings.database == "opsdesk_product_dev"
    assert settings.host == "127.0.0.1"


def test_database_settings_reads_different_prefixes(monkeypatch):
    monkeypatch.setenv("OPSDESK_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("OPSDESK_DB_PORT", "5432")
    monkeypatch.setenv("OPSDESK_DB_DATABASE", "opsdesk_product_dev")
    monkeypatch.setenv("OPSDESK_DB_USERNAME", "app_user")
    monkeypatch.setenv("OPSDESK_DB_PASSWORD", "app_pass")

    monkeypatch.setenv("OPSDESK_TEST_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("OPSDESK_TEST_DB_PORT", "5432")
    monkeypatch.setenv("OPSDESK_TEST_DB_DATABASE", "opsdesk_product_test")
    monkeypatch.setenv("OPSDESK_TEST_DB_USERNAME", "test_user")
    monkeypatch.setenv("OPSDESK_TEST_DB_PASSWORD", "test_pass")

    app_settings = DatabaseSettings()
    test_settings = IntegrationDatabaseSettings()

    assert app_settings.database == "opsdesk_product_dev"
    assert test_settings.database == "opsdesk_product_test"


def test_database_settings_repr_masks_password():
    synthetic_password = "super-secret-synthetic-password"
    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password=synthetic_password,
    )

    repr_str = repr(settings)
    assert synthetic_password not in repr_str


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("connect_timeout_seconds", 0),
        ("connect_timeout_seconds", 1),
        ("connect_timeout_seconds", 31),
        ("pool_timeout_seconds", -1),
        ("pool_timeout_seconds", 0),
        ("pool_timeout_seconds", 31),
    ],
)
def test_database_settings_rejects_invalid_timeouts(field, value):
    values = {
        "host": "127.0.0.1",
        "port": 5432,
        "database": "opsdesk_product_dev",
        "username": "dev_user",
        "password": "synthetic-test-password",
        field: value,
    }

    with pytest.raises(ValidationError) as exc_info:
        DatabaseSettings(**values)

    assert any(error["loc"] == (field,) for error in exc_info.value.errors())


def test_database_settings_reads_timeout_environment(monkeypatch):
    monkeypatch.setenv("OPSDESK_DB_CONNECT_TIMEOUT_SECONDS", "7")
    monkeypatch.setenv("OPSDESK_DB_POOL_TIMEOUT_SECONDS", "9")

    settings = DatabaseSettings(
        host="127.0.0.1",
        port=5432,
        database="opsdesk_product_dev",
        username="dev_user",
        password="synthetic-test-password",
    )

    assert settings.connect_timeout_seconds == 7
    assert settings.pool_timeout_seconds == 9
