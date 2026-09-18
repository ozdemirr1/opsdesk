from pathlib import Path

import pytest


@pytest.mark.parametrize("failure_on_delete", [1, 2])
@pytest.mark.parametrize("driver_error", [False, True])
def test_cleanup_failure_stops_test_execution(
    pytester, monkeypatch, failure_on_delete, driver_error
):
    synthetic_password = "cleanup-secret-marker-9284"
    synthetic_url = (
        f"postgresql+psycopg://fake_user:{synthetic_password}@127.0.0.1/fake_database"
    )

    monkeypatch.setenv("PROBE_FAKE_PASSWORD", synthetic_password)
    monkeypatch.setenv("PROBE_FAKE_URL", synthetic_url)

    original_conftest = (
        Path(__file__)
        .parent.joinpath("integration", "conftest.py")
        .read_text(encoding="utf-8")
    )

    mock_fixture = """
from unittest.mock import MagicMock
import pytest
import os
from sqlalchemy.exc import OperationalError

@pytest.fixture
def integration_engine():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn

    state = {"delete_count": 0}

    def mock_execute(statement, *args, **kwargs):
        if "DELETE FROM public.integration_probe" in str(statement):
            state["delete_count"] += 1
            if state["delete_count"] == %d:
                if %r:
                    detail = (
                        os.environ["PROBE_FAKE_PASSWORD"]
                        + " "
                        + os.environ["PROBE_FAKE_URL"]
                    )
                    raise OperationalError(None, None, RuntimeError(detail))
                raise RuntimeError("Synthetic cleanup failure")
        return MagicMock()

    conn.execute.side_effect = mock_execute
    return engine
""" % (failure_on_delete, driver_error)

    pytester.makeconftest(original_conftest + "\n" + mock_fixture)

    pytester.makepyfile(
        """
        from pathlib import Path

        def test_one(probe_scope):
            with probe_scope() as factory:
                raise RuntimeError("Synthetic body failure")

        def test_two():
            Path("second_test_ran.txt").touch()
        """
    )

    result = pytester.runpytest_subprocess(
        "-q",
        "--tb=native",
        "--no-showlocals",
        "--maxfail=0",
        "-o",
        "addopts=",
        timeout=30,
    )

    assert result.ret == pytest.ExitCode.INTERRUPTED

    output = "\n".join(result.stdout.lines + result.stderr.lines)

    assert synthetic_password not in output
    assert synthetic_url not in output

    if driver_error:
        assert "RuntimeError: Database operation failed." in output
    else:
        assert "RuntimeError: Synthetic cleanup failure" in output

    assert "Probe cleanup failed; stopping to preserve test isolation." in output

    assert not (pytester.path / "second_test_ran.txt").exists()

    if failure_on_delete == 2:
        assert "RuntimeError: Synthetic body failure" in output
        assert "ExceptionGroup: Probe body and cleanup failed." in output


@pytest.mark.parametrize("failure_mode", ["before", "after", "revision"])
def test_identity_cleanup_failure_stops_execution(pytester, monkeypatch, failure_mode):
    synthetic_secret = "identity-cleanup-secret-marker"
    monkeypatch.setenv("IDENTITY_FAKE_SECRET", synthetic_secret)
    monkeypatch.setenv("IDENTITY_FAILURE_MODE", failure_mode)

    original_conftest = (
        Path(__file__)
        .parent.joinpath("integration", "conftest.py")
        .read_text(encoding="utf-8")
    )

    mock_fixture = """
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError


@pytest.fixture
def integration_engine():
    engine = MagicMock()
    connection = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection

    mode = os.environ["IDENTITY_FAILURE_MODE"]
    delete_count = 0

    def execute(statement, *args, **kwargs):
        nonlocal delete_count
        sql = str(statement)

        if sql == "SELECT version_num FROM public.alembic_version":
            result = MagicMock()
            result.scalar_one.return_value = (
                "unexpected-revision" if mode == "revision" else "6a3066cd5538"
            )
            return result

        if sql.startswith("DELETE FROM public."):
            delete_count += 1
            Path("delete_count.txt").write_text(
                str(delete_count), encoding="utf-8"
            )

            failure_at = 1 if mode == "before" else 4
            if delete_count == failure_at:
                raise OperationalError(
                    None,
                    None,
                    RuntimeError(os.environ["IDENTITY_FAKE_SECRET"]),
                )
            return MagicMock()

        raise AssertionError("Unexpected database statement.")

    connection.execute.side_effect = execute
    return engine
"""

    pytester.makeconftest(original_conftest + "\n" + mock_fixture)
    pytester.makepyfile(
        """
        from pathlib import Path

        def test_one(identity_scope):
            with identity_scope():
                Path("body_entered.txt").touch()
                raise RuntimeError("Synthetic identity body failure")

        def test_two():
            Path("second_test_ran.txt").touch()
        """
    )

    result = pytester.runpytest_subprocess(
        "-q",
        "--tb=native",
        "--no-showlocals",
        "--maxfail=0",
        "-o",
        "addopts=",
        timeout=30,
    )

    output = "\n".join(result.stdout.lines + result.stderr.lines)

    assert result.ret == pytest.ExitCode.INTERRUPTED
    assert "Identity cleanup failed; stopping to preserve test isolation." in output
    assert synthetic_secret not in output
    assert not (pytester.path / "second_test_ran.txt").exists()

    body_entered = (pytester.path / "body_entered.txt").exists()
    assert body_entered is (failure_mode == "after")

    delete_counter = pytester.path / "delete_count.txt"

    if failure_mode == "revision":
        assert not delete_counter.exists()
        assert "Unexpected schema revision for identity cleanup." in output
    else:
        expected_deletes = "1" if failure_mode == "before" else "4"
        assert delete_counter.read_text(encoding="utf-8") == expected_deletes
        assert "RuntimeError: Database operation failed." in output

    if failure_mode == "after":
        assert "RuntimeError: Synthetic identity body failure" in output
        assert "ExceptionGroup: Identity body and cleanup failed." in output
