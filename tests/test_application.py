from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import Engine

import opsdesk.main as main_module
from opsdesk.config import Settings
from opsdesk.identity.token_config import TokenSettings
from opsdesk.main import create_app

TEST_JWT_SECRET = "test-only-jwt-secret-with-at-least-32-bytes"


def test_app_with_docs_enabled():
    settings = Settings(environment="test", docs_enabled=True)
    app = create_app(settings)

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        assert docs_response.status_code == 200

        openapi_response = client.get("/openapi.json")
        assert openapi_response.status_code == 200

        openapi_data = openapi_response.json()
        assert openapi_data["info"]["title"] == "OpsDesk"


def test_app_with_docs_disabled():
    settings = Settings(environment="test", docs_enabled=False)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        assert client.get("/docs").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/openapi.json").status_code == 404


def test_invalid_environment_prevents_app_creation(monkeypatch):
    monkeypatch.setenv("OPSDESK_ENVIRONMENT", "invalid-environment-marker")
    monkeypatch.setenv("OPSDESK_DOCS_ENABLED", "true")

    with pytest.raises(ValidationError) as exc_info:
        create_app()

    error_text = str(exc_info.value)
    assert "environment" in error_text
    assert "invalid-environment-marker" not in error_text


def test_explicit_settings_override_environment(monkeypatch):
    monkeypatch.setenv("OPSDESK_ENVIRONMENT", "invalid-environment-marker")
    monkeypatch.setenv("OPSDESK_DOCS_ENABLED", "false")

    settings = Settings(environment="test", docs_enabled=True)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        assert docs_response.status_code == 200


def test_non_test_app_disposes_the_engine_it_creates(monkeypatch):
    database_settings = object()
    engine = Mock(spec=Engine)
    factory = Mock()

    database_settings_constructor = Mock(
        return_value=database_settings,
    )
    engine_constructor = Mock(return_value=engine)
    session_factory_constructor = Mock(return_value=factory)

    monkeypatch.setattr(
        main_module,
        "DatabaseSettings",
        database_settings_constructor,
    )
    monkeypatch.setattr(
        main_module,
        "create_database_engine",
        engine_constructor,
    )
    monkeypatch.setattr(
        main_module,
        "create_session_factory",
        session_factory_constructor,
    )

    app = main_module.create_app(
        Settings(environment="development"),
        token_settings=TokenSettings(secret=TEST_JWT_SECRET),
    )

    assert app.state.session_factory is factory
    engine.dispose.assert_not_called()

    with TestClient(app):
        pass

    database_settings_constructor.assert_called_once_with()
    engine_constructor.assert_called_once_with(database_settings)
    session_factory_constructor.assert_called_once_with(engine)
    engine.dispose.assert_called_once_with()


def test_explicit_token_configuration_builds_shared_login_context(monkeypatch):
    token_settings = TokenSettings(secret=TEST_JWT_SECRET)
    token_clock = Mock(
        return_value=datetime(2026, 9, 26, 9, 30, tzinfo=UTC),
    )
    password_hasher = Mock()
    password_hasher.create_dummy_hash.return_value = "dummy-password-hash"
    password_hasher_constructor = Mock(return_value=password_hasher)

    monkeypatch.setattr(
        main_module,
        "PasswordHasher",
        password_hasher_constructor,
    )

    app = create_app(
        Settings(environment="test"),
        token_settings=token_settings,
        token_clock=token_clock,
    )

    assert app.state.token_settings is token_settings
    assert app.state.token_clock is token_clock
    assert app.state.login_password_hasher is password_hasher
    assert app.state.dummy_password_hash == "dummy-password-hash"

    password_hasher_constructor.assert_called_once_with()
    password_hasher.create_dummy_hash.assert_called_once_with()


def test_non_test_app_loads_jwt_secret_from_environment(monkeypatch):
    password_hasher = Mock()
    password_hasher.create_dummy_hash.return_value = "dummy-password-hash"

    monkeypatch.setenv(
        "OPSDESK_JWT_SECRET",
        TEST_JWT_SECRET,
    )
    monkeypatch.setattr(
        main_module,
        "PasswordHasher",
        Mock(return_value=password_hasher),
    )

    app = create_app(
        Settings(environment="development"),
        session_factory=Mock(),
    )

    assert app.state.token_settings.secret.get_secret_value() == TEST_JWT_SECRET
    assert app.state.login_password_hasher is password_hasher
    assert app.state.dummy_password_hash == "dummy-password-hash"
