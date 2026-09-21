import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from opsdesk.config import Settings
from opsdesk.main import create_app

SECRET = "synthetic-private-marker"


class ExampleInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    email: str


@pytest.fixture
def client():
    app = create_app(Settings(environment="test"))

    @app.post("/test-input/{organization_id}")
    def accept_input(
        organization_id: int,
        payload: ExampleInput,
        limit: int = 20,
    ):
        return {"accepted": True}

    @app.get("/test-http/{status_code}")
    def fail(status_code: int):
        raise HTTPException(
            status_code=status_code,
            detail=SECRET,
            headers={"X-Private": SECRET},
        )

    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "content_type",
    ["application/json", "application/json; charset=utf-8", "Application/JSON"],
)
def test_json_media_types_are_accepted(client, content_type):
    response = client.post(
        "/test-input/1",
        content='{"email": "example@example.com"}',
        headers={"Content-Type": content_type},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "content_type",
    [None, "text/plain", "application/xml", "application/problem+json"],
)
def test_unsupported_media_types_are_rejected(client, content_type):
    headers = {} if content_type is None else {"Content-Type": content_type}
    response = client.post(
        "/test-input/1",
        content='{"email": "example@example.com"}',
        headers=headers,
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


@pytest.mark.parametrize("body", [b'{"email":', b'{"email":"\xff"}'])
def test_malformed_json_is_safe(client, body):
    response = client.post(
        "/test-input/1",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["error"] == {
        "code": "invalid_json",
        "message": "Request body is not valid JSON.",
        "details": [],
    }


@pytest.mark.parametrize(
    ("url", "payload", "expected_field"),
    [
        ("/test-input/1", {}, "body.email"),
        ("/test-input/1", {"email": 123}, "body.email"),
        (f"/test-input/{SECRET}", {"email": "a"}, "path.organization_id"),
        (f"/test-input/1?limit={SECRET}", {"email": "a"}, "query.limit"),
        ("/test-input/1", {"email": "a", SECRET: SECRET}, "body"),
    ],
)
def test_validation_uses_safe_field_details(client, url, payload, expected_field):
    response = client.post(url, json=payload)

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert error["message"] == "Request validation failed."
    assert len(error["details"]) == 1
    assert error["details"][0]["field"] == expected_field
    assert set(error["details"][0]) == {"field", "message"}
    assert SECRET not in response.text


def test_empty_body_is_validation_error(client):
    response = client.post("/test-input/1", content=b"")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_validation_details_are_bounded(client):
    payload = {"email": "a", **{f"{SECRET}-{i}": SECRET for i in range(30)}}
    response = client.post("/test-input/1", json=payload)

    assert response.status_code == 422
    assert len(response.json()["error"]["details"]) == 20
    assert SECRET not in response.text


def test_unknown_route_does_not_echo_path(client):
    response = client.get(f"/{SECRET}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert SECRET not in response.text


def test_wrong_method_preserves_allow_header(client):
    response = client.get("/test-input/1")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "POST" in response.headers["allow"]


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [
        (401, "unauthenticated"),
        (403, "permission_denied"),
        (400, "http_error"),
        (500, "internal_error"),
    ],
)
def test_http_exception_detail_and_private_headers_are_not_exposed(
    client, status_code, expected_code
):
    response = client.get(f"/test-http/{status_code}")

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["details"] == []
    assert SECRET not in response.text
    assert "x-private" not in response.headers

    if status_code == 401:
        assert response.headers["www-authenticate"] == "Bearer"
