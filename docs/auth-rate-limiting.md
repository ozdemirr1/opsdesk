# Authentication rate limiting

Implemented locally on 24 November for the planned 21 November learning slice.
Disabled by default; this is not a hosted rollout. JWT/session semantics remain
unchanged. The existing routes are POST /auth/login and POST /users (registration).

## Contract and architecture

After valid body parsing, before credential verification or account creation,
the route calls the limiter. Service dependency construction can occur earlier;
limiter rejection prevents the business method, not all framework setup work.
Login allows 5 admitted attempts per 60 seconds per IP; registration allows 3 per
600 seconds per IP. Successful and unsuccessful admitted attempts both count.
Invalid request bodies do not consume this quota. The first admitted request starts
a fixed-duration window; rejected requests do not refresh it.

A short Redis EVAL script checks state, admits/increments and establishes expiry
without interleaving another request. Existing counters must be positive canonical
integers within the configured limit and have a valid TTL. Invalid state produces
a safe 503 without repairing or resetting the counter. Lua is atomic with respect
to other commands, not an automatic rollback mechanism.

Exhaustion returns the existing JSON error envelope with code rate_limited, HTTP
429 and Retry-After (remaining milliseconds rounded up to seconds, minimum 1).
Redis errors, malformed replies and missing/invalid client addresses return safe
service_unavailable 503 and skip the business method. There is no per-process
fallback or automatic retry. Only fixed event names are logged.

## Keys and client addresses

Keys include environment, policy version, operation and SHA-256 of the canonical
IP. IPv4-mapped IPv6 uses the equivalent IPv4 identity. Hashing avoids raw IP text
in keys but is NOT anonymization: the IPv4 space is enumerable. No password,
email, token or raw key is logged. Login and registration quotas are independent.
Shared public IPs share quota; distributed sources can bypass IP-only protection.

The application uses request.client.host, not client-supplied forwarded headers.
This address can already have been rewritten by Uvicorn. Direct local runs should
use --no-proxy-headers. Behind a proxy, explicitly configure --proxy-headers and
--forwarded-allow-ips for only verified proxy peers; do not trust '*' on an endpoint
reachable directly by clients. The proxy must sanitize forwarded headers. Tests
exercise direct spoofing and Uvicorn trusted/untrusted peers; no live proxy address
or hosted trust configuration has been selected or changed.

## Settings and deployment boundary

Environment prefix: OPSDESK_AUTH_LIMIT_. No env file is loaded automatically.

| Suffix | Default |
| --- | --- |
| ENABLED | false |
| HOST | 127.0.0.1 |
| PORT | 6379 |
| PASSWORD | unset; supply only at runtime if needed |
| TIMEOUT_SECONDS | 0.2 (connect and socket, each operation) |
| LOGIN_LIMIT / LOGIN_WINDOW_SECONDS | 5 / 60 |
| REGISTER_LIMIT / REGISTER_WINDOW_SECONDS | 3 / 600 |

Pool maximum is 10 connections, retry count is zero, client closes at app shutdown.
Timeout is not an end-to-end request deadline. Settings are independent of the
statistics cache. This does not provision a separate Redis instance. Limiter state
must not be treated as disposable cache: eviction/restart can reset quota even
though errors fail closed. Dedicated capacity/eviction policy, TLS, trusted proxy
configuration and hosted enablement require separate review. Changing limits while
old counters exist can yield 503 until their TTL expires; coordinate policy changes.

## Verification

Unit/API tests check admission ordering, success/failure counting, malformed bodies,
429 and 503, safe errors, canonical IPs, spoofing, Uvicorn trust and client lifecycle.
Opt-in tests/integration/test_auth_limit_redis.py uses an isolated loopback Redis
port with unique synthetic namespaces; never use development Redis. It verifies
10 concurrent attempts admit exactly 3, expiry, non-refreshing rejections, corrupt
counter failure and real-Redis HTTP enforcement. Corrupt lab keys receive expiry;
no database flush or resource deletion. Redis CI remains the planned 22 November
work, so these tests are not claimed as current remote CI evidence.

References: [Redis scripting](https://redis.io/docs/latest/develop/programmability/eval-intro/)
and [Uvicorn proxy settings](https://uvicorn.dev/settings/).
