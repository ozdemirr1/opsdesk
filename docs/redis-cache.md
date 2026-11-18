# Optional Ticket statistics cache

Implemented for the planned 18 November exercise on 19 November 2026.
This is a local learning increment. Cache is disabled by default; post-commit
invalidation and stale-fill race handling remain the next exercise. Do not enable
this increment in the hosted preview.

## Request flow

The existing authenticated endpoint checks fresh active actor, membership and
Organization state before every Redis GET. Its key includes environment, contract
version, Organization, actor, membership and own/all visibility. Cache hits skip
Ticket aggregation, not authorization queries. A role demotion changes the key;
inactive membership is denied before cache access.

On a miss, the original aggregate reads access and counts in one SQL snapshot.
Cache writes use the scope returned by that snapshot and occur only when it
matches the initial scope. This prevents a between-query role change from writing
an all-Tickets result under an own-Tickets key. It does not solve the separate
post-commit stale-fill race or guarantee immediate revocation after a request's
last authorization snapshot.

Malformed, oversized (>4096 bytes), negative, incomplete or inconsistent cached
responses are treated as misses. A read failure falls back to the DB and skips
the cache write for that request. A write failure preserves the DB response.
Only fixed cache event names are logged; no keys, payloads, credentials or raw
connection exceptions are included.

## Configuration

All settings use the `OPSDESK_STATS_CACHE_` prefix and environment variables.
No env file is loaded automatically.

| Suffix | Default | Purpose |
| --- | --- | --- |
| ENABLED | false | Explicit local opt-in |
| HOST | 127.0.0.1 | Redis endpoint; use service name inside Compose |
| PORT | 6379 | Redis port |
| PASSWORD | unset | Optional runtime secret, never committed |
| TTL_SECONDS | 30 | Initial freshness/load tradeoff; allowed 1–300 |
| TIMEOUT_SECONDS | 0.2 | Connect and socket timeout; allowed 0.05–1 |

The client uses a pool capped at 10 connections and zero automatic retries.
Timeouts apply per network operation, not as an absolute whole-request deadline;
DNS and DB work are outside that limit. The application closes its owned client
on lifespan shutdown. TLS/live-provider configuration is outside this local slice.

## Verification

`tests/test_ticket_stats_cache.py` covers hit/miss, authorization ordering, scoped
keys, role changes between queries, zero counts, bad data and read/write failures.
The PostgreSQL read suite observes actual aggregate SQL execution on miss versus
hit and checks demotion against the database. Its cache transport is an in-memory
fake; real Redis transport/expiry checks are separate.

`tests/integration/test_stats_redis.py` requires an isolated loopback Redis lab on
an ephemeral non-default port, `OPSDESK_RUN_REDIS_TESTS=1` and
`OPSDESK_REDIS_LAB_PORT`. It uses unique synthetic keys with one-second expiry and
never flushes a database. It checks expiry, invalid JSON and a TCP peer that never
replies. The ordinary PostgreSQL CI does not opt into Redis tests yet; Redis CI is
planned for 22 November. Never use the development Redis as this lab target.
