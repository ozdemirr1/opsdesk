import pytest
from fastapi.testclient import TestClient

from opsdesk.api.errors import ApiError
from opsdesk.config import Settings
from opsdesk.main import create_app


@pytest.mark.parametrize(
    ("code", "status_code"),
    [
        ("unauthenticated", 401),
        ("organization_access_denied", 403),
        ("ticket_not_found", 404),
        ("permission_denied", 403),
        ("organization_suspended", 403),
        ("validation_error", 422),
        ("state_conflict", 409),
        ("membership_exists", 409),
        ("user_not_addable", 400),
        ("email_already_exists", 409),
        ("invalid_json", 400),
        ("unsupported_media_type", 415),
        ("internal_error", 500),
        ("not_found", 404),
        ("method_not_allowed", 405),
    ],
)
def test_api_error_http_contract(code, status_code):
    app = create_app(Settings(environment="test"))

    @app.get("/test-error")
    def fail():
        raise ApiError(code)

    with TestClient(app) as client:
        response = client.get("/test-error")

    assert response.status_code == status_code
    assert response.headers["content-type"] == "application/json"

    payload = response.json()
    assert set(payload) == {"error"}
    assert set(payload["error"]) == {"code", "message", "details"}
    assert payload["error"]["code"] == code
    assert isinstance(payload["error"]["message"], str)
    assert payload["error"]["message"]
    assert payload["error"]["details"] == []

    if code == "unauthenticated":
        assert response.headers["www-authenticate"] == "Bearer"
    else:
        assert "www-authenticate" not in response.headers


def test_api_error_does_not_expose_its_original_cause(caplog):
    synthetic_secret = "password-token-secret-marker"
    app = create_app(Settings(environment="test"))

    @app.get("/test-conflict")
    def fail():
        try:
            raise RuntimeError(synthetic_secret)
        except RuntimeError as exc:
            raise ApiError("email_already_exists") from exc

    with TestClient(app) as client:
        response = client.get("/test-conflict")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "email_already_exists",
            "message": "Email already exists.",
            "details": [],
        }
    }
    assert synthetic_secret not in response.text
    assert synthetic_secret not in caplog.text
