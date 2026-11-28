# Optional Ticket statistics cache

Implemented for the planned 18 November exercise on 19 November 2026.
Extended on 21 November for the planned 19 November generation exercise.
Cache remains disabled by default. Hosted enablement is a separate decision.

## Request flow

The existing authenticated endpoint checks fresh active actor, membership and
Organization state before every Redis GET. Its key includes environment, contract
version, Organization, actor, membership and own/all visibility. Cache hits skip
Ticket aggregation, not authorization queries. A role demotion changes the key;
inactive membership is denied before cache access.

On a miss, the original aggregate reads access and counts in one SQL snapshot.
Cache writes use the scope returned by that snapshot and occur only when it
matches the initial scope. This prevents a between-query role change from writing
an all-Tickets result under an own-Tickets key. It does not guarantee immediate revocation after a request's
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
replies. PostgreSQL CI keeps these opt-in Redis tests separate. The isolated
[Redis CI workflow](redis-ci.md) now runs both cache and limiter integration
modules; its verified recovery run passed all ten cases. Never use development
Redis as this lab target.

## Post-commit generation invalidation

Version 2 result keys also contain an Organization generation token. Authorization
runs before generation access. A reader captures the token before SQL aggregation
and always fills that same generation; it never fetches a new token for an old
result. Successful Ticket creation rotates the Organization token after commit,
covering all customer and staff result keys. Rollback does not rotate it. Priority
changes do not alter status counts and do not invalidate these results.

Missing tokens are initialized with a fresh random UUID using SET NX. A losing
initializer reads the winner's token. Generation metadata expires after twice the
result TTL; expiration or eviction creates a new random token, never a reset
counter that could reactivate old results. Invalid/unavailable generation data
bypasses cache. Old result keys expire naturally; no key scan or bulk deletion.

A deterministic SQL interleaving test commits creation after an old count but
before its cache fill. The next read uses the new generation and sees the new
count. A separate real Redis test verifies token rotation and old-key isolation.

This is best-effort freshness, not an atomic PostgreSQL/Redis transaction. A process
can stop after commit or Redis rotation can fail. Creation still succeeds and must
not be retried because of that cache failure. Existing stale entries then expire
by their own TTL; a delayed reader may fill one later, so TTL is not a hard bound
measured from commit. Concurrent in-flight reads can return older snapshots.
Durable invalidation delivery and stronger consistency are outside this slice.
