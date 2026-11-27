# Isolated Redis CI

Prepared on 27 November for the planned 22 November learning slice. Remote run
verification is pending publication; this document does not claim a successful run.

The Redis CI workflow starts a fresh redis:8.2.11-bookworm service for its own job.
A redis-cli ping health check gates readiness. Tests execute directly on the runner
and connect to loopback using job.services.redis.ports[6379], not a remembered local
port or a Compose service name. No development/hosted Redis or repository secrets
are used. Only the two explicit Redis integration modules run; PostgreSQL guarded
suites remain separate. Unique synthetic key namespaces prevent test collisions.

OPSDESK_RUN_REDIS_TESTS=1 opts in. The JUnit XML check requires tests > 0 and zero
failures/errors/skips, so a missing opt-in cannot silently make this job green.
The upload step runs after test failure as well as success; it does not suppress
the pytest failure. Only redis-tests.xml is uploaded, retained for seven days.
No environment dump, full workspace or credential file is uploaded.

Dependency cache (for example the existing frontend npm cache) speeds installation.
An artifact is a run output, here a test report. Application Redis cache stores
runtime-derived counts. A CI cache miss should permit normal dependency install;
a failing Redis integration fixture is a different condition and must fail the job.

Next learning evidence: inspect a real run and its downloaded XML, diagnose an
isolated wrong-port failure, then verify recovery. No live provider, Redis memory
policy or Celery broker is configured by this workflow.
