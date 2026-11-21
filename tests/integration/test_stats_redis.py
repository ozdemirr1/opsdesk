"""Opt-in adapter checks against a separately started, loopback-only Redis lab."""

import os
import socket
import threading
import time
from uuid import uuid4

import pytest

from opsdesk.tickets.read_models import TicketStats
from opsdesk.tickets.stats_cache import StatsCacheSettings, create_cache

pytestmark = pytest.mark.integration


@pytest.fixture
def cache():
    if os.environ.get("OPSDESK_RUN_REDIS_TESTS") != "1":
        pytest.skip("Requires the isolated Redis lab")
    port = int(os.environ["OPSDESK_REDIS_LAB_PORT"])
    if port == 6379:
        pytest.fail("Use a separate ephemeral lab port, not the default Redis port")
    result = create_cache(
        StatsCacheSettings(host="127.0.0.1", port=port, ttl_seconds=1),
        "test-" + uuid4().hex,
    )
    try:
        assert result.client.ping()
        yield result
    finally:
        result.close()


def test_real_redis_miss_hit_expiry_and_invalid_payload(cache):
    key = cache.key(42, 10, (101, "customer"), cache.generation(10))
    stats = TicketStats(0, dict(open=0, in_progress=0, resolved=0, closed=0))
    assert cache.get(key) == (None, True)
    cache.put(key, stats)
    assert cache.get(key) == (stats, True)
    assert 0 <= cache.client.ttl(key) <= 1
    deadline = time.monotonic() + 3
    while cache.client.exists(key) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert cache.get(key) == (None, True)
    cache.client.set(key, "invalid-json", ex=1)
    assert cache.get(key) == (None, True)


def test_unresponsive_tcp_peer_has_bounded_timeout(cache, caplog):
    # The peer accepts TCP but never speaks Redis. Only this test owns the socket.
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        listener.settimeout(2)
        finished = threading.Event()

        def peer():
            try:
                connection, _ = listener.accept()
                with connection:
                    finished.wait(2)
            except TimeoutError:
                pass

        worker = threading.Thread(target=peer)
        worker.start()
        stalled = create_cache(
            StatsCacheSettings(port=listener.getsockname()[1]), "test"
        )
        try:
            started = time.monotonic()
            assert stalled.get("test:timeout") == (None, False)
            elapsed = time.monotonic() - started
            assert 0.1 <= elapsed < 2
            assert "read_unavailable" in caplog.text
        finally:
            stalled.close()
            finished.set()
            worker.join(timeout=3)


def test_real_generation_rotation_isolates_delayed_fill(cache):
    old_generation = cache.generation(10)
    cache.invalidate(10)
    current_generation = cache.generation(10)
    assert current_generation != old_generation
    old_key = cache.key(42, 10, (101, "customer"), old_generation)
    current_key = cache.key(42, 10, (101, "customer"), current_generation)
    old_stats = TicketStats(2, dict(open=2, in_progress=0, resolved=0, closed=0))
    cache.put(old_key, old_stats)
    assert cache.get(current_key) == (None, True)
    assert cache.get(old_key) == (old_stats, True)
    assert 0 <= cache.client.ttl(cache.generation_key(10)) <= 2
