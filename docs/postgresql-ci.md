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

## Evidence

13 November: implementation prepared; CI execution results pending. The earlier
PostgreSQL learning workflow at a8e82ca passed its connection and job-order exercise;
it did not run these product suites. Schema/data counts must come from this workflow.
