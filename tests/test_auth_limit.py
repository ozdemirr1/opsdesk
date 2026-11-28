import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError, TimeoutError
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from opsdesk.api.errors import ApiError
from opsdesk.config import Settings
from opsdesk.identity.dependencies import get_login_service, get_registration_service
from opsdesk.identity.models import User
from opsdesk.identity.rate_limit import (
    AuthLimiter,
    AuthLimitSettings,
    create_auth_limiter,
)
from opsdesk.identity.services import EmailAlreadyExistsError, InvalidCredentialsError
from opsdesk.main import create_app


class Store:
    def __init__(self, reply=None, error=None):
        self.reply = reply if reply is not None else [1, 1, 60000]
        self.error = error
        self.calls = []

    def eval(self, *args):
        self.calls.append(args)
        if self.error:
            raise self.error
        return self.reply

    def close(self):
        pass


class Service:
    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def login(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return "synthetic-token"

    def register_user(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return User(
            user_id=42,
            email="user@example.com",
            password_hash="synthetic",
            is_active=True,
        )


def application(store, service):
    app = create_app(Settings(environment="test"))
    app.state.auth_limiter = AuthLimiter(store, AuthLimitSettings(), "test")
    app.dependency_overrides[get_login_service] = lambda: service
    app.dependency_overrides[get_registration_service] = lambda: service
    return app


BODY = {"email": "user@example.com", "password": "river valley lantern"}


@pytest.mark.parametrize("path,limit", [("/auth/login", 5), ("/users", 3)])
def test_exhaustion_prevents_business_operation_and_sets_retry(path, limit):
    store, service = Store([0, limit, 1501]), Service()
    with TestClient(application(store, service), client=("192.0.2.1", 1234)) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"
    assert response.json()["error"]["code"] == "rate_limited"
    assert service.calls == 0


@pytest.mark.parametrize("path", ["/auth/login", "/users"])
@pytest.mark.parametrize(
    "error", [ConnectionError("private-marker"), TimeoutError("private-marker")]
)
def test_store_outage_fails_closed(path, error, caplog):
    store, service = Store(error=error), Service()
    with TestClient(application(store, service), client=("192.0.2.1", 1234)) as client:
        response = client.post(path, json=BODY)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "retry-after" not in response.headers
    assert service.calls == 0
    assert "private-marker" not in response.text + caplog.text


@pytest.mark.parametrize("path", ["/auth/login", "/users"])
def test_invalid_body_does_not_consume_quota(path):
    store, service = Store(), Service()
    with TestClient(application(store, service)) as client:
        assert client.post(path, json={}).status_code == 422
    assert not store.calls
    assert service.calls == 0


@pytest.mark.parametrize(
    "path,error,status",
    [
        ("/auth/login", None, 200),
        ("/auth/login", InvalidCredentialsError(), 401),
        ("/users", None, 201),
        ("/users", EmailAlreadyExistsError(), 409),
    ],
)
def test_success_and_failure_both_consume_admission(path, error, status):
    store, service = Store(), Service(error)
    with TestClient(application(store, service), client=("192.0.2.1", 1234)) as client:
        assert client.post(path, json=BODY).status_code == status
    assert len(store.calls) == service.calls == 1


@pytest.mark.parametrize(
    "trusted,expected", [("10.0.0.1", "192.0.2.1"), ("192.0.2.1", "198.51.100.2")]
)
def test_forwarded_address_requires_trusted_transport_peer(trusted, expected):
    store, service = Store(), Service()
    app = application(store, service)
    wrapped = ProxyHeadersMiddleware(app, trusted_hosts=[trusted])
    with TestClient(wrapped, client=("192.0.2.1", 1234)) as client:
        assert (
            client.post(
                "/auth/login", json=BODY, headers={"X-Forwarded-For": "198.51.100.2"}
            ).status_code
            == 200
        )
    assert store.calls[0][2] == app.state.auth_limiter.key("login", expected)


def test_forged_headers_do_not_change_direct_connection_key():
    store, service = Store(), Service()
    with TestClient(application(store, service), client=("192.0.2.1", 1234)) as client:
        for host in ["198.51.100.1", "198.51.100.2"]:
            client.post("/auth/login", json=BODY, headers={"X-Forwarded-For": host})
    assert store.calls[0][2] == store.calls[1][2]


@pytest.mark.parametrize(
    "reply", [None, [], [True, 1, 60000], [0, 1, 60000], [1, 6, 5], [1, 1, -1]]
)
def test_malformed_store_reply_fails_closed(reply):
    store = Store()
    store.reply = reply
    with pytest.raises(ApiError) as error:
        AuthLimiter(store, AuthLimitSettings(), "test").check("login", "192.0.2.1")
    assert error.value.code == "service_unavailable"


def test_key_is_canonical_and_separates_operations_and_clients():
    limiter = AuthLimiter(Store(), AuthLimitSettings(), "test")
    key = limiter.key("login", "192.0.2.1")
    assert key == limiter.key("login", "::ffff:192.0.2.1")
    assert key != limiter.key("register", "192.0.2.1")
    assert key != limiter.key("login", "192.0.2.2")
    assert "192.0.2.1" not in key


@pytest.mark.parametrize("host", [None, "unknown"])
def test_missing_or_invalid_client_address_fails_closed(host):
    store = Store()
    with pytest.raises(ApiError) as error:
        AuthLimiter(store, AuthLimitSettings(), "test").check("login", host)
    assert error.value.code == "service_unavailable"
    assert not store.calls


def test_opt_in_client_lifecycle_and_bounded_wait():
    limiter = create_auth_limiter(AuthLimitSettings(), "test")
    try:
        options = limiter.client.connection_pool.connection_kwargs
        assert options["socket_timeout"] == options["socket_connect_timeout"] == 0.2
        assert options["retry"].get_retries() == 0
    finally:
        limiter.close()
    app = create_app(Settings(environment="test"))
    assert app.state.auth_limiter is None


def test_owned_limiter_is_created_only_when_enabled_and_closed(monkeypatch):
    import opsdesk.main as main

    events = []

    class Owned:
        def close(self):
            events.append("closed")

    def factory(settings, environment):
        events.append((settings.enabled, environment))
        return Owned()

    monkeypatch.setattr(main, "create_auth_limiter", factory)
    with TestClient(
        create_app(
            Settings(environment="test"),
            auth_limit_settings=AuthLimitSettings(enabled=True),
        )
    ):
        assert events == [(True, "test")]
    assert events == [(True, "test"), "closed"]
