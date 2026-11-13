"""CI preflight must fail before any migration or destructive test."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / "ci" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bootstrap_refuses_local_execution(monkeypatch):
    module = load_script("bootstrap_postgresql")
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    docker = Mock()
    monkeypatch.setattr(module, "docker", docker)
    with pytest.raises(SystemExit, match="disposable GitHub-hosted"):
        module.main()
    docker.assert_not_called()


@pytest.mark.parametrize(
    "mismatch", ["database", "role", "address", "port", "superuser"]
)
def test_connected_target_rejected_before_migration(monkeypatch, mismatch):
    module = load_script("run_postgresql")
    monkeypatch.setattr(module.sys, "argv", ["run_postgresql.py", "schema"])
    monkeypatch.setattr(
        module,
        "IntegrationDatabaseSettings",
        lambda: Mock(username="opsdesk_product_test_runner"),
    )
    target = ["opsdesk_product_test", "opsdesk_product_test_runner", "127.0.0.1", 5432]
    replacements = {
        "database": (0, "opsdesk_product_dev"),
        "role": (1, "postgres"),
        "address": (2, "172.20.0.3"),
        "port": (3, 5433),
    }
    if mismatch in replacements:
        index, value = replacements[mismatch]
        target[index] = value
    connection = Mock()
    connection.execute.return_value.one.side_effect = [
        tuple(target),
        (True, False, False, False, False),
    ]
    from unittest.mock import MagicMock

    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(module, "create_integration_engine", lambda settings: engine)
    upgrade = Mock()
    monkeypatch.setattr(module.command, "upgrade", upgrade)
    with pytest.raises(SystemExit):
        module.main()
    upgrade.assert_not_called()
    engine.dispose.assert_called_once()
