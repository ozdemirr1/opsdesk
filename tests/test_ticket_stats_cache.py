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

    def set(self, key, value, ex):
        if self.write_error:
            raise ConnectionError("private-host")
        self.sets.append((key, ex))
        self.values[key] = value


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
    assert client.sets[0][1] == 30
    repo.access = TicketReadAccess(True, False, True)
    with pytest.raises(TicketOrganizationAccessDeniedError):
        call(service)
    assert len(client.gets) == 2


def test_user_org_and_role_scope_never_share_cached_result():
    repo, client, service = setup()
    call(service)
    call(service, actor=43)
    call(service, org=11)
    repo.scope = (101, "agent")
    call(service)
    assert repo.reads == 4
    assert len(set(client.gets)) == 4


def test_scope_change_between_access_and_aggregate_does_not_cache():
    repo, client, service = setup()
    repo.result_scope = (101, "agent")
    assert call(service).total == 2
    assert not client.sets


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
    client.values[
        "opsdesk:test:ticket-stats:v1:org:10:user:42:membership:101:scope:own"
    ] = value
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
