# OpsDesk

OpsDesk is a multi-tenant support ticket management API designed for B2B
environments. Each organization has its own membership and data-access boundary.

## Problem

Support requests tracked through scattered messages are difficult to follow.
Customers lack visibility into progress, while support teams struggle to track
responsibility, conversations, and resolution status. OpsDesk aims to solve this
by providing a centralized system where each organization's data remains isolated
and actions follow explicit permission rules.

## Target Users

- **Customer:** Submits support requests and follows permitted tickets.
- **Agent:** Handles permitted tickets and communicates with customers.
- **Admin:** Manages support operations and permitted membership actions within
  an organization.
- **Owner:** Holds organization ownership and manages ownership-level actions.

## Planned Capabilities

The API is currently being designed to support the following core workflows:

- Global user identities linked to organization-specific memberships and roles.
- Organization data isolation enforced by the backend.
- Ticket lifecycle rules for `open`, `in_progress`, `resolved`, and `closed`.
- Ticket assignment and role-based access control (RBAC), combined with
  organization and ticket-level permission checks.
- Permission-controlled ticket comments. Attachment metadata remains a domain-design
  topic; its API and file storage are deferred beyond Month 03.

## Project Status

Backend foundation implementation is underway. The repository now contains a
FastAPI application factory, validated application settings, and tests covering
application startup/shutdown, documentation visibility, and configuration behavior.
Synchronous database configuration, engine/session factories, and guarded local
PostgreSQL integration tests are implemented. Business tables, migrations,
business endpoints, and authentication are not implemented.
File-content upload and storage remain outside the Month 03 scope.

See [Product requirements](docs/requirements.md) for the initial scope,
acceptance scenarios, and unresolved design decisions.
See [Domain model](docs/domain-model.md) for the shared vocabulary, entity
lifecycles, invariants, and reviewed Week 09 domain policies.
See the [relational model](docs/relational-model.md) and [ERD](docs/erd.md) for
the proposed tables, relationship keys, constraints, and remaining design work.
See the [access-control matrix](docs/access-control.md) and
[Ticket lifecycle](docs/ticket-lifecycle.md) for reviewed role/resource permissions,
state transitions, and acceptance scenarios.
See the [API contract baseline](docs/api-contract.md) for the 22-endpoint inventory,
response examples, errors, pagination, release exclusions, and remaining decisions.
Business-feature implementation and unresolved decisions are tracked in the published backlog.

See the [Week 09 issue plan](docs/issue-plan.md) for the 26 published GitHub issues,
priorities/dependencies, coverage of all 22 endpoints, and the proposed Week 10
sequence. GitHub tracks current work status; local issue files preserve the initial
published scope. Publication does not imply completed design tasks or implementation.


## Local Development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) before running
these commands from the repository root. The supported Python series is 3.14;
`.python-version` pins the development interpreter to 3.14.7. Dependencies are
recorded in `pyproject.toml`, with resolved versions in `uv.lock`.

Install runtime and development dependencies from the lockfile:

```bash
uv sync --locked
```

Start the development server:

```bash
uv run uvicorn opsdesk.main:create_app --factory --reload
```

With the default settings, open [Swagger UI](http://127.0.0.1:8000/docs),
[ReDoc](http://127.0.0.1:8000/redoc), or the
[OpenAPI document](http://127.0.0.1:8000/openapi.json). The schema currently has no
business operations. Stop the server with Ctrl+C.

Run linting, formatting checks, and tests:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run pytest -q
```

To apply formatting locally, use `uv run ruff format src tests`.

## Configuration

Settings are validated when the application factory creates its configuration.
They use the `OPSDESK_` environment-variable prefix. No environment variable is
currently required: the application starts with defaults without database or
authentication services. `.env` files are not loaded automatically.

| Environment variable | Accepted values | Default |
| --- | --- | --- |
| `OPSDESK_ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `OPSDESK_DOCS_ENABLED` | Boolean values parsed by Pydantic; use `true` or `false` | `true` |

`OPSDESK_ENVIRONMENT` labels the environment; selecting `production` does not
implicitly disable documentation or apply deployment security settings.
`OPSDESK_DOCS_ENABLED=false` disables `/docs`, `/redoc`, and `/openapi.json`.
For example:

```bash
OPSDESK_ENVIRONMENT=production OPSDESK_DOCS_ENABLED=false uv run uvicorn opsdesk.main:create_app --factory
```

This command demonstrates configuration only; it is not a production deployment
recipe. Invalid supported setting values prevent application creation. Validation
error text hides input values, but this is not a guarantee for every structured
error or logging format. Never log raw configuration or credentials.

Tests can pass an explicit `Settings` instance to `create_app(settings=...)`.
Explicit field values take precedence over environment variables; tests that
exercise environment loading control those variables with pytest's `monkeypatch`.


## Continuous Integration

The `Backend CI` workflow in `.github/workflows/ci.yml` is configured to run on
pushes and pull requests. It uses an Ubuntu runner, uv 0.12.3, and the Python version
pinned in `.python-version`. Dependency installation requires the committed lockfile.
The workflow token has read-only repository-content permissions, and checkout does
not retain Git credentials for subsequent commands.

The job checks Ruff linting and formatting, then runs only the application and
configuration tests. A failed check fails the job. PostgreSQL integration tests,
Docker builds, and deployment are outside this workflow's scope. No application
secrets or developer `.env` file are required.

Reproduce the checks locally:

```bash
uv sync --locked
uv run --locked ruff check src tests
uv run --locked ruff format --check src tests
uv run --locked pytest -q tests/test_application.py tests/test_config.py
```

Inspect actual run results in the repository's GitHub Actions tab. Workflow
configuration and passing local checks do not establish a successful hosted run.


### Temporary test warning filter

Starlette 1.6.0 references `anyio.abc.BlockingPortal`, deprecated by the installed
AnyIO version. The upstream development branch uses `anyio.from_thread.BlockingPortal`,
but the latest published Starlette release checked on 16 September 2026 is still 1.6.0.
Pytest temporarily filters only that exact `DeprecationWarning` message from
`starlette.testclient`; other warnings remain visible. This manages test output and
does not patch the dependency or change runtime behavior.

Remove the filter when a compatible published Starlette release includes the fix,
then run the complete test suite without the exception. Do not edit installed
packages or downgrade dependencies solely to hide this warning.

References: [Starlette releases](https://starlette.dev/release-notes/) and
[upstream TestClient](https://github.com/Kludex/starlette/blob/main/starlette/testclient.py).


## Product Database Targets

Decision reviewed on 16 September 2026: the standalone OpsDesk project uses
`opsdesk_product_dev` for development and `opsdesk_product_test` for integration
tests on `127.0.0.1:5432`. The older `opsdesk_dev` and `opsdesk_test` databases
belong to the Month 02 learning application and must not be renamed or cleaned
by this project.

Provision separate local roles: `opsdesk_product_app` owns the development
database; `opsdesk_product_test_runner` owns the test database. Neither role
should be a superuser or have CREATEDB/CREATEROLE privileges. Restrict access to
the new databases to their respective owners. These are local development roles;
production migration/runtime privilege separation is outside this setup.

Keep the existing `OPSDESK_DB_` and `OPSDESK_TEST_DB_` environment prefixes.
The integration guard must accept only the exact new test target and reject
`opsdesk_test`, `opsdesk_dev`, and `opsdesk_product_dev`, as well as any other
database or server target. Never log credentials or full connection URLs.

Local provisioning was completed on 16 September 2026. Read-only verification
confirmed database ownership, non-superuser roles, and denied cross-access between
the two product roles/databases. Guard and engine tests reject the old learning
databases. Local verification on 16 September passed 37 non-database tests and
six explicitly enabled PostgreSQL tests, including real-commit visibility, cleanup,
rollback, and connection release. These results do not establish business-schema
correctness or hosted database CI.

### Reproducing the local PostgreSQL setup

The reviewed commands are preserved in
[`scripts/postgresql/bootstrap_local.sql`](scripts/postgresql/bootstrap_local.sql).
This is an administrator-run, one-time provisioning script for a fresh local
PostgreSQL server target. It creates roles and empty databases; future application
tables are managed through Alembic migrations, not this script.

The current machine is already provisioned: do not rerun bootstrap here. The
script aborts before creation if any named product role or database already exists.
It never drops, renames, or resets an existing database. Provisioning is not atomic:
if a later command fails, inspect the partial state before deciding how to resume.
Do not run it concurrently, from CI, or with `--single-transaction`.

On a fresh setup, from the repository root, connect with your local PostgreSQL
administrator role:

```bash
psql -X -h 127.0.0.1 -p 5432 -U YOUR_LOCAL_ADMIN -d postgres \
  -v ON_ERROR_STOP=1 -f scripts/postgresql/bootstrap_local.sql
```

Replace `YOUR_LOCAL_ADMIN` with your own administrator role. Then open an
interactive administrator session to set two distinct passwords:

```bash
psql -X -h 127.0.0.1 -p 5432 -U YOUR_LOCAL_ADMIN -d postgres
```

At the psql prompt, run these commands individually and enter passwords only at
the hidden prompts:

```text
\password opsdesk_product_app
\password opsdesk_product_test_runner
\q
```

Never put real passwords in SQL files, shell commands, logs, or Git. PostgreSQL's
server authentication configuration also controls authentication; creating a role
and setting its password does not by itself establish a password-authentication
policy. Application credentials will be supplied through the corresponding
`OPSDESK_DB_*` / `OPSDESK_TEST_DB_*` environment variables.

References: [CREATE DATABASE](https://www.postgresql.org/docs/18/sql-createdatabase.html)
and [psql](https://www.postgresql.org/docs/18/app-psql.html).


### Database configuration and test execution

`DatabaseSettings` uses `OPSDESK_DB_`; `IntegrationDatabaseSettings` uses
`OPSDESK_TEST_DB_`. Both require `HOST`, `PORT`, `DATABASE`, `USERNAME`, and
`PASSWORD` when instantiated. Port must be in 1..65535; other values must be
non-empty. Neither configuration loads `.env` automatically. These settings are
separate from the application factory's current database-free startup.

In a local **zsh** terminal, configure the integration suite:

```zsh
export OPSDESK_TEST_DB_HOST=127.0.0.1
export OPSDESK_TEST_DB_PORT=5432
export OPSDESK_TEST_DB_DATABASE=opsdesk_product_test
export OPSDESK_TEST_DB_USERNAME=opsdesk_product_test_runner
read -rs "OPSDESK_TEST_DB_PASSWORD?Test database password: "
printf '\n'
export OPSDESK_TEST_DB_PASSWORD
OPSDESK_RUN_INTEGRATION_TESTS=1 uv run pytest -q tests/integration
```

The password is entered at a hidden prompt, not embedded in shell history.
Unset it after the session with `unset OPSDESK_TEST_DB_PASSWORD`.
Without `OPSDESK_RUN_INTEGRATION_TESTS=1`, ordinary `uv run pytest -q` skips the
six integration tests. With opt-in enabled, missing/invalid configuration or a
failed connection fails the run rather than silently skipping it. The real
connection test verifies the database, role, server address, and port.

### Transaction ownership and isolation

- `session_scope` always closes its Session; callers explicitly commit their work.
  Closing a Session rolls back unfinished work and returns its connection to the
  pool. It cannot undo a completed commit. The integration engine is disposed in
  fixture teardown.
- Run only one suite at a time against this database. Parallel/overlapping runs
  are unsupported; no cross-process lock is implemented.
- The target guard runs before engine creation and probe setup/cleanup. Only
  `public.integration_probe` is created for these infrastructure tests. Its rows
  are deleted before and after each isolated probe scope in separate committed
  transactions. No business tables or migration-history records are cleaned.
- Tests close their Sessions before cleanup. Real commits are checked from separate
  Sessions; uncommitted writes, exception cleanup, and pool return are also tested.
- Cleanup failure is surfaced and stops subsequent tests. If the body and teardown
  both fail, an `ExceptionGroup` retains both failures. Subprocess tests exercise
  failures before and after the body and prove the next test does not execute.
- A forcibly terminated process may not run teardown. The next validated scope's
  initial cleanup removes leftover probe rows. Future business tables require
  Alembic migrations and an explicitly reviewed cleanup allowlist.

### Database error reporting boundary

Engine SQL echo is disabled and SQL parameters are hidden. Connection verification
and probe SQLAlchemy failures are translated into fixed messages without displayed
exception chaining. Synthetic-secret tests cover connection/statement failures,
captured logs/output, and cleanup-failure reports.

Pytest uses `--tb=native --no-showlocals`: standard Python tracebacks retain failure
locations and exception groups without pytest's enhanced argument/local-value
rendering. This reporting policy is part of the tested boundary. Changing to
`--tb=long`, enabling local-value output, or adding custom exception serialization
requires a new disclosure review. `raise ... from None` suppresses displayed
chaining; it does not erase the original exception or sensitive objects in memory.
These checks are not a universal guarantee for future application logs or HTTP
errors; shared API error/logging work remains issue #10.

The existing hosted CI still selects only the seven foundation tests. The expanded
non-database suite needs a separate CI-selection update; PostgreSQL CI remains #25.
