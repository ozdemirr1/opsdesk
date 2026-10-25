from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from opsdesk.config import Settings
from opsdesk.main import create_app


def test_liveness_works_without_database_or_authentication():
    app = create_app(
        settings=Settings(environment="test", docs_enabled=False),
    )

    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_200_and_closes_session():
    session = Mock(spec=Session)
    session.scalar.return_value = 1
    factory = Mock(return_value=session)
    app = create_app(
        settings=Settings(environment="test"),
        session_factory=factory,
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    session.close.assert_called_once()


def test_readiness_returns_503_without_session_factory():
    app = create_app(settings=Settings(environment="test"))

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "Service is temporarily unavailable.",
            "details": [],
        }
    }


@pytest.mark.parametrize("failure_point", ["factory", "query"])
def test_readiness_hides_database_errors_and_closes_session(failure_point, caplog):
    marker = "synthetic-db-secret"
    error = OperationalError("SELECT 1", {}, RuntimeError(marker))
    session = Mock(spec=Session)
    factory = Mock(return_value=session)

    if failure_point == "factory":
        factory.side_effect = error
    else:
        session.scalar.side_effect = error

    app = create_app(
        settings=Settings(environment="test"),
        session_factory=factory,
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")
        live_response = client.get("/health/live")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert marker not in response.text
    assert marker not in caplog.text
    assert live_response.status_code == 200

    if failure_point == "query":
        session.close.assert_called_once()
    else:
        session.close.assert_not_called()


def test_readiness_rejects_unexpected_probe_result():
    session = Mock(spec=Session)
    session.scalar.return_value = None
    app = create_app(
        settings=Settings(environment="test"),
        session_factory=Mock(return_value=session),
    )

    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    session.close.assert_called_once()
