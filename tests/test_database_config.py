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
