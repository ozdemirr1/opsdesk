import pytest
from pydantic import ValidationError

from opsdesk.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("OPSDESK_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OPSDESK_DOCS_ENABLED", raising=False)

    settings = Settings()

    assert settings.environment == "development"
    assert settings.docs_enabled is True


def test_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("OPSDESK_ENVIRONMENT", "test")
    monkeypatch.setenv("OPSDESK_DOCS_ENABLED", "false")

    settings = Settings()

    assert settings.environment == "test"
    assert settings.docs_enabled is False


def test_invalid_docs_enabled_is_rejected(monkeypatch):
    monkeypatch.setenv("OPSDESK_ENVIRONMENT", "test")
    monkeypatch.setenv("OPSDESK_DOCS_ENABLED", "not-a-boolean")

    with pytest.raises(ValidationError):
        Settings()
