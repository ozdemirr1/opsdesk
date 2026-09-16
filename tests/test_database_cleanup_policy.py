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
