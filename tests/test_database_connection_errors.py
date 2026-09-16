import traceback
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from opsdesk.db.connection import DatabaseConnectionError, verify_database_connection


@pytest.mark.parametrize("failure_point", ["connect", "execute"])
def test_verify_database_connection_hides_sensitive_info(caplog, capsys, failure_point):
    synthetic_password = "super_secret_synthetic_password"
    synthetic_url = f"postgresql+psycopg://user:{synthetic_password}@127.0.0.1/db"

    original_error = OperationalError(
        None,
        None,
        RuntimeError(f"{synthetic_password} {synthetic_url}"),
    )

    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_context_manager = MagicMock()

    mock_engine.connect.return_value = mock_context_manager
    mock_context_manager.__enter__.return_value = mock_connection
    mock_context_manager.__exit__.return_value = False

    if failure_point == "connect":
        mock_engine.connect.side_effect = original_error
    else:
        mock_connection.execute.side_effect = original_error

    with pytest.raises(DatabaseConnectionError) as exc_info:
        verify_database_connection(mock_engine)

    assert str(exc_info.value) == "Database connection failed."

    rendered = "".join(traceback.format_exception(exc_info.value))
    assert synthetic_password not in rendered
    assert synthetic_url not in rendered

    assert synthetic_password not in caplog.text
    assert synthetic_url not in caplog.text

    captured = capsys.readouterr()
    assert synthetic_password not in captured.out
    assert synthetic_url not in captured.out
    assert synthetic_password not in captured.err
    assert synthetic_url not in captured.err

    if failure_point == "execute":
        mock_context_manager.__exit__.assert_called_once()
