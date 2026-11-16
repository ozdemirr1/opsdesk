# PostgreSQL CI

The schema job and dependent data job each receive a fresh PostgreSQL 18 service.
They do not share database state. Existing backend/frontend/image workflows remain
separate. This workflow builds no deployment and uses no repository or production
secrets, including on pull requests.

The Python test container shares its PostgreSQL service network namespace via
`--network container:<service-id>`. This preserves both the configured target and
server-side `inet_server_addr()` guard at `127.0.0.1:5432`. No port is published.
The source checkout is mounted read-only; Linux dependencies live in `/tmp` inside
the test container. No local `.env`, virtualenv, Compose volume or hosted DB is used.

Bootstrap is restricted to GitHub-hosted runners. The service initially uses trust
only to initialize this disposable environment. Before tests, bootstrap creates
only `opsdesk_product_test` and its restricted owner `opsdesk_product_test_runner`,
generates a random password, then replaces TCP trust with loopback SCRAM and rejects
bridge connections. Local socket administration remains inside the service.
The password is masked and stored in a mode-600 runner temporary env file; bootstrap
SQL/errors are not printed. Existing roles/databases cause failure, never a reset.

Before migration, the test entry point verifies the actual database, role, server
address/port and absence of administrative role flags. Existing wrong-target unit
tests prove rejection before engine creation. It then migrates to head, explicitly
enables only the selected suite, and checks model/schema drift after success.
Schema failure prevents the data job from running via `needs: schema`.

GitHub disposes its runner and service resources after the job. This workflow does
not remove local resources. Do not run bootstrap against development or hosted DBs.

## Evidence — 13 November 2026

The initial implementation at 02abc71 failed during temporary env-file creation:
`Path.open()` does not accept `opener`. No product suite ran, and `needs` skipped
the data job. [Failed run](https://github.com/ozdemirr1/opsdesk/actions/runs/43417330187).
Recovery 72ee274 uses built-in `open()` and adds a mode-600 file-creation test.

[PostgreSQL CI](https://github.com/ozdemirr1/opsdesk/actions/runs/43417456376)
passed 5 schema tests (0.64s), then 281 data tests (26.00s), with no Alembic drift.
Each job also passed 17 existing target/connection unit checks and verified its
actual DB, role, loopback address and non-administrative role flags before migration.
Schema completed at 11:29:52 UTC; the independent data job started at 11:29:55 UTC.
Backend CI passed 783 tests / 286 deselected at the same commit; frontend and Docker
CI also passed. These are separate suites, not a combined test count.

The learning workflow at a8e82ca separately passed the connection/job-order example.
Learner Compose queries showed server address 127.0.0.1 from the DB container and
172.20.0.3 from the API, explaining the shared-network choice without relaxing guards.

No development/hosted destructive tests, local resource deletion, main merge or
production release occurred. Q03/Week 18 acceptance and learner review remain open.
