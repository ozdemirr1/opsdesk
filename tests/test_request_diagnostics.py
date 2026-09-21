import asyncio
import json
import logging
from uuid import UUID

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from opsdesk.api.errors import ApiError
from opsdesk.api.middleware import LOGGER_NAME, RequestDiagnosticsMiddleware
from opsdesk.config import Settings
from opsdesk.main import create_app

SECRET = "synthetic-password-token-marker"


@pytest.fixture
def client(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    app = create_app(Settings(environment="test"))

    @app.get("/test-observe/{item_id}")
    def observe(item_id: int):
        return {"ok": True}

    @app.get("/test-auth")
    def require_auth():
        raise ApiError("unauthenticated")

    @app.get("/test-failure/{kind}")
    def fail(kind: str):
        if kind == "database":
            raise OperationalError(
                None,
                None,
                RuntimeError(f"postgresql://user:{SECRET}@localhost/private"),
            )
        raise RuntimeError(SECRET)

    @app.get("/test-request-id")
    def read_request_id(request: Request):
        return {"request_id": request.state.request_id}

    with TestClient(app) as test_client:
        yield test_client


def request_events(caplog):
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == LOGGER_NAME
    ]


@pytest.mark.parametrize(
    ("url", "status", "route"),
    [
        ("/test-observe/42", 200, "/test-observe/{item_id}"),
        (f"/test-observe/{SECRET}", 422, "/test-observe/{item_id}"),
        (f"/missing-{SECRET}", 404, "<unmatched>"),
        ("/test-auth", 401, "/test-auth"),
    ],
)
def test_response_and_log_share_safe_request_id(client, caplog, url, status, route):
    response = client.get(
        url,
        params={"token": SECRET},
        headers={"Authorization": f"Bearer {SECRET}"},
    )

    assert response.status_code == status
    request_id = response.headers["x-request-id"]
    assert UUID(request_id).version == 4

    events = request_events(caplog)
    assert len(events) == 1
    event = events[0]
    assert event["request_id"] == request_id
    assert event["route"] == route
    assert event["method"] == "GET"
    assert event["status_code"] == status
    assert event["duration_ms"] >= 0
    assert event["response_started"] is True
    assert event["unexpected_error"] is False
    assert SECRET not in json.dumps(events)

    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", ["runtime", "database"])
def test_unexpected_errors_are_safe_and_observable(client, caplog, kind):
    response = client.get(f"/test-failure/{kind}")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "An unexpected error occurred.",
            "details": [],
        }
    }

    events = request_events(caplog)
    assert len(events) == 1
    assert events[0]["request_id"] == response.headers["x-request-id"]
    assert events[0]["status_code"] == 500
    assert events[0]["unexpected_error"] is True
    assert SECRET not in response.text
    assert SECRET not in caplog.text
    assert "postgresql://" not in caplog.text


@pytest.mark.parametrize(
    "incoming_id",
    ["client-selected-id", "x" * 4096, SECRET],
)
def test_incoming_request_id_is_ignored(client, caplog, incoming_id):
    response = client.get(
        "/test-request-id",
        headers={"X-Request-ID": incoming_id},
    )

    generated_id = response.headers["x-request-id"]
    assert UUID(generated_id).version == 4
    assert generated_id != incoming_id
    assert response.json()["request_id"] == generated_id
    assert request_events(caplog)[0]["request_id"] == generated_id
    assert incoming_id not in json.dumps(request_events(caplog))


def test_each_request_gets_a_distinct_id(client):
    first = client.get("/test-request-id")
    second = client.get("/test-request-id")

    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_non_http_scope_passes_through():
    received = []

    async def application(scope, receive, send):
        received.append(scope["type"])

    async def receive():
        return {"type": "lifespan.startup"}

    async def send(message):
        pass

    middleware = RequestDiagnosticsMiddleware(application)
    asyncio.run(middleware({"type": "lifespan"}, receive, send))

    assert received == ["lifespan"]


def test_failure_after_response_start_is_not_replaced(caplog):
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    messages = []

    async def application(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        raise RuntimeError(SECRET)

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    middleware = RequestDiagnosticsMiddleware(application)

    with pytest.raises(
        RuntimeError,
        match=r"^Response failed after start\.$",
    ):
        asyncio.run(
            middleware(
                {"type": "http", "method": "GET"},
                receive,
                send,
            )
        )

    assert len(messages) == 1
    assert messages[0]["status"] == 200

    event = request_events(caplog)[0]
    assert event["status_code"] == 200
    assert event["response_started"] is True
    assert event["unexpected_error"] is True
    assert SECRET not in caplog.text
