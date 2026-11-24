"""Opt-in isolated Redis tests; never target development Redis."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest

from opsdesk.api.errors import ApiError
from opsdesk.identity.rate_limit import AuthLimitSettings, create_auth_limiter

pytestmark = pytest.mark.integration


@pytest.fixture
def limiter():
    if os.environ.get("OPSDESK_RUN_REDIS_TESTS") != "1":
        pytest.skip("Requires isolated Redis lab")
    port = int(os.environ["OPSDESK_REDIS_LAB_PORT"])
    assert port != 6379
    result = create_auth_limiter(
        AuthLimitSettings(port=port, login_limit=3, login_window_seconds=2),
        "test-" + uuid4().hex,
    )
    try:
        assert result.client.ping()
        yield result
    finally:
        result.close()


def test_parallel_admission_and_expiry(limiter):
    barrier = Barrier(10)

    def attempt(_):
        barrier.wait(timeout=5)
        try:
            limiter.check("login", "192.0.2.1")
            return True
        except ApiError as error:
            assert error.code == "rate_limited"
            assert 1 <= error.retry_after <= 2
            return False

    with ThreadPoolExecutor(max_workers=10) as pool:
        outcomes = list(pool.map(attempt, range(10)))
    assert sum(outcomes) == 3
    key = limiter.key("login", "192.0.2.1")
    assert limiter.client.get(key) == b"3"
    before = limiter.client.pttl(key)
    with pytest.raises(ApiError):
        limiter.check("login", "192.0.2.1")
    assert 0 <= limiter.client.pttl(key) <= before <= 2000
    deadline = time.monotonic() + 5
    while limiter.client.exists(key):
        assert time.monotonic() < deadline
        time.sleep(0.02)
    limiter.check("login", "192.0.2.1")
    assert limiter.client.get(key) == b"1"


@pytest.mark.parametrize(
    "value,expiry",
    [("1", None), ("bad", 2000), ("-1", 2000), ("1.5", 2000), ("01", 2000)],
)
def test_corrupt_counter_fails_closed_without_mutation(limiter, value, expiry):
    key = limiter.key("login", "192.0.2.1")
    limiter.client.set(key, value, px=expiry)
    try:
        with pytest.raises(ApiError) as error:
            limiter.check("login", "192.0.2.1")
        assert error.value.code == "service_unavailable"
        assert limiter.client.get(key) == value.encode()
    finally:
        limiter.client.pexpire(key, 1000)


def test_http_enforcement_uses_real_redis_and_preserves_errors(limiter):
    from fastapi.testclient import TestClient

    from opsdesk.config import Settings
    from opsdesk.identity.dependencies import (
        get_login_service,
        get_registration_service,
    )
    from opsdesk.identity.models import User
    from opsdesk.main import create_app

    class Service:
        calls = 0

        def login(self, **kwargs):
            self.calls += 1
            return "synthetic-token"

        def register_user(self, **kwargs):
            self.calls += 1
            return User(
                user_id=42,
                email="lab@example.com",
                password_hash="synthetic",
                is_active=True,
            )

    service = Service()
    app = create_app(Settings(environment="test"))
    app.state.auth_limiter = limiter
    app.dependency_overrides[get_login_service] = lambda: service
    app.dependency_overrides[get_registration_service] = lambda: service
    payload = {"email": "lab@example.com", "password": "river valley lantern"}
    # Avoid an expiry during HTTP setup; thresholds remain three per operation.
    limiter.settings.login_window_seconds = 60
    with TestClient(app, client=("192.0.2.1", 1234)) as client:
        for index in range(3):
            assert (
                client.post(
                    "/auth/login",
                    json=payload,
                    headers={"X-Forwarded-For": f"198.51.100.{index + 1}"},
                ).status_code
                == 200
            )
        response = client.post("/auth/login", json=payload)
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1
        assert service.calls == 3
        assert client.post("/users", json=payload).status_code == 201
        key = limiter.key("register", "192.0.2.1")
        limiter.client.set(key, "bad", px=1000)
        assert client.post("/users", json=payload).status_code == 503
        assert service.calls == 4
