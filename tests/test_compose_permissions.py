from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from opsdesk.db import compose_permissions


@pytest.mark.parametrize("failure", [None, "identity", "sql"])
def test_grants_require_verified_identity_and_close_engine(monkeypatch, failure):
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    monkeypatch.setattr(compose_permissions, "ComposeMigrationSettings", MagicMock())
    monkeypatch.setattr(
        compose_permissions, "create_compose_migration_engine", lambda _: engine
    )
    verified = False

    def verify(conn):
        nonlocal verified
        assert conn is connection
        if failure == "identity":
            raise ValueError("wrong identity")
        verified = True

    def execute(statement):
        assert verified
        if failure == "sql":
            raise OperationalError(None, None, RuntimeError("secret-marker"))

    monkeypatch.setattr(compose_permissions, "verify_compose_connection", verify)
    connection.exec_driver_sql.side_effect = execute
    if failure:
        with pytest.raises(
            ValueError if failure == "identity" else RuntimeError
        ) as caught:
            compose_permissions.main()
        assert "secret-marker" not in str(caught.value)
        if failure == "identity":
            connection.exec_driver_sql.assert_not_called()
    else:
        compose_permissions.main()
        statements = " ".join(
            c.args[0] for c in connection.exec_driver_sql.call_args_list
        )
        assert "public.comments" in statements
        assert "UPDATE (priority, updated_at)" in statements
        assert "alembic_version" not in statements
        assert "ALL TABLES" not in statements
        assert "DELETE" not in statements
        assert "TRUNCATE" not in statements
    engine.dispose.assert_called_once()
