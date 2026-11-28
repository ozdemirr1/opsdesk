import json

import pytest
from redis.exceptions import ConnectionError, TimeoutError

from opsdesk.tickets.read_models import TicketReadAccess, TicketStatsRead
from opsdesk.tickets.services import (
    TicketOrganizationAccessDeniedError,
    TicketReadService,
)
from opsdesk.tickets.stats_cache import (
    StatsCacheSettings,
    TicketStatsCache,
    create_cache,
)


class Client:
    def __init__(self):
        self.values = {}
        self.gets = []
        self.sets = []
        self.error = None
        self.write_error = False

    def get(self, key):
        self.gets.append(key)
        if self.error:
            raise self.error
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if self.write_error:
            raise ConnectionError("private-host")
        if nx and key in self.values:
            return False
        self.sets.append((key, ex))
        self.values[key] = value
        return True


class Repository:
    def __init__(self):
        self.access = TicketReadAccess(True, True, True)
        self.scope = (101, "customer")
        self.result_scope = None
        self.reads = 0
        self.authorizations = 0
        self.counts = {"open": 2}

    def stats_access_for_actor(self, **kwargs):
        self.authorizations += 1
        return TicketStatsRead(self.access, {}, self.scope)

    def stats_for_actor(self, **kwargs):
        self.reads += 1
        return TicketStatsRead(
            self.access, self.counts, self.result_scope or self.scope
        )


def call(service, actor=42, org=10):
    return service.stats_for_actor(actor_user_id=actor, organization_id=org)


def setup():
    repo, client = Repository(), Client()
    cache = TicketStatsCache(client, "test", 30)
    return repo, client, TicketReadService(repo, cache)


def test_hit_skips_aggregation_but_never_authorization():
    repo, client, service = setup()
    assert call(service).total == call(service).total == 2
    assert repo.reads == 1
    assert repo.authorizations == 2
    assert client.sets[-1][1] == 30
    repo.access = TicketReadAccess(True, False, True)
    with pytest.raises(TicketOrganizationAccessDeniedError):
        call(service)
    assert len(client.gets) == 4


def test_user_org_and_role_scope_never_share_cached_result():
    repo, client, service = setup()
    call(service)
    call(service, actor=43)
    call(service, org=11)
    repo.scope = (101, "agent")
    call(service)
    assert repo.reads == 4
    assert len({key for key in client.gets if ":user:" in key}) == 4


def test_scope_change_between_access_and_aggregate_does_not_cache():
    repo, client, service = setup()
    repo.result_scope = (101, "agent")
    assert call(service).total == 2
    assert not [key for key, _ in client.sets if ":user:" in key]


@pytest.mark.parametrize(
    "error", [ConnectionError("private-host"), TimeoutError("private-token")]
)
def test_read_outage_falls_back_without_attempting_write(error, caplog):
    repo, client, service = setup()
    client.error = error
    assert call(service).total == 2
    assert repo.reads == 1
    assert not client.sets
    assert "read_unavailable" in caplog.text
    assert "private-" not in caplog.text


def test_write_outage_does_not_lose_database_result(caplog):
    repo, client, service = setup()
    service._stats_cache.generation(10)
    client.write_error = True
    assert call(service).total == 2
    assert "write_unavailable" in caplog.text
    assert "private-host" not in caplog.text


@pytest.mark.parametrize(
    "value",
    [
        b"bad json",
        b"x" * 4097,
        json.dumps(
            {
                "total": 99,
                "by_status": {"open": 1, "closed": 0, "resolved": 0, "in_progress": 0},
            }
        ),
        json.dumps({"total": -1, "by_status": {}}),
        json.dumps(
            {
                "total": 1,
                "by_status": {
                    "open": True,
                    "closed": 0,
                    "resolved": 0,
                    "in_progress": 0,
                },
            }
        ),
    ],
)
def test_invalid_cache_is_a_miss(value, caplog):
    repo, client, service = setup()
    cache = service._stats_cache
    generation = cache.generation(10)
    client.values[cache.key(42, 10, repo.scope, generation)] = value
    assert call(service).total == 2
    assert repo.reads == 1
    assert "invalid_value" in caplog.text


def test_zero_counts_are_hits():
    repo, client, service = setup()
    repo.counts = {}
    assert call(service).total == call(service).total == 0
    assert repo.reads == 1


def test_client_has_bounded_timeouts_and_no_retries():
    cache = create_cache(StatsCacheSettings(), "test")
    try:
        options = cache.client.connection_pool.connection_kwargs
        assert options["socket_connect_timeout"] == options["socket_timeout"] == 0.2
        assert options["retry"].get_retries() == 0
        assert cache.client.connection_pool.max_connections == 10
    finally:
        cache.close()


def test_delayed_fill_stays_in_old_generation():
    repo, client, service = setup()
    cache = service._stats_cache
    original = repo.stats_for_actor

    def interleaved_read(**kwargs):
        old = original(**kwargs)
        repo.counts = {"open": 3}
        cache.invalidate(10)
        return old

    repo.stats_for_actor = interleaved_read
    assert call(service).total == 2
    repo.stats_for_actor = original
    assert call(service).total == 3
    assert call(service).total == 3
    assert repo.reads == 2


def test_lost_generation_never_reactivates_old_results():
    repo, client, service = setup()
    assert call(service).total == 2
    cache = service._stats_cache
    previous = cache.generation(10)
    del client.values[cache.generation_key(10)]
    repo.counts = {"open": 3}
    assert call(service).total == 3
    assert cache.generation(10) != previous


def test_initialization_loser_uses_winners_generation():
    client = Client()
    cache = TicketStatsCache(client, "test", 30)
    winner = "a" * 32

    def competing_set(key, value, **kwargs):
        client.values[key] = winner
        return False

    client.set = competing_set
    assert cache.generation(10) == winner


def test_invalid_generation_bypasses_result_cache():
    repo, client, service = setup()
    client.values[service._stats_cache.generation_key(10)] = b"invalid"
    assert call(service).total == 2
    assert not client.sets
    assert len(client.gets) == 1
