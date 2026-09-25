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
PostgreSQL integration tests are implemented. The initial Alembic migration and
persistence models now cover Users, Organizations, and OrganizationMemberships.
Constraint and isolated migration-cycle tests cover this schema. `POST /users`
implements the first identity slice with strict request validation, canonical email
storage, Argon2id password hashing, explicit transaction handling, and a safe duplicate
email response. Login, JWT/current-user authentication, Organization/Ticket endpoints,
and Ticket tables are not implemented.
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

Set all five `OPSDESK_DB_` connection variables described below, then start the
development server:

```bash
uv run uvicorn opsdesk.main:create_app --factory --reload --no-access-log
```

Open [Swagger UI](http://127.0.0.1:8000/docs),
[ReDoc](http://127.0.0.1:8000/redoc), or the
[OpenAPI document](http://127.0.0.1:8000/openapi.json). The schema includes the
`POST /users` registration operation. Stop the server with Ctrl+C.

Run linting, formatting checks, and tests:

```bash
uv run ruff check src tests migrations
uv run ruff format --check src tests migrations
uv run pytest -q
```

To apply formatting locally, use `uv run ruff format src tests migrations`.

## Configuration

Application settings are validated when the application factory creates its
configuration and use the `OPSDESK_` prefix. A non-test application also creates its
database engine and requires all five `OPSDESK_DB_` connection variables below.
`.env` files are not loaded automatically.

| Environment variable | Accepted values | Default |
| --- | --- | --- |
| `OPSDESK_ENVIRONMENT` | `development`, `test`, `production` | `development` |
| `OPSDESK_DOCS_ENABLED` | Boolean values parsed by Pydantic; use `true` or `false` | `true` |

| Database environment variable | Requirement |
| --- | --- |
| `OPSDESK_DB_HOST` | Required non-empty host |
| `OPSDESK_DB_PORT` | Required integer from 1 through 65535 |
| `OPSDESK_DB_DATABASE` | Required non-empty database name |
| `OPSDESK_DB_USERNAME` | Required non-empty role name |
| `OPSDESK_DB_PASSWORD` | Required non-empty secret; never commit or log it |

`OPSDESK_ENVIRONMENT` labels the environment; selecting `production` does not
implicitly disable documentation or apply deployment security settings.
`OPSDESK_DOCS_ENABLED=false` disables `/docs`, `/redoc`, and `/openapi.json`.
For example:

```bash
OPSDESK_ENVIRONMENT=production OPSDESK_DOCS_ENABLED=false uv run uvicorn opsdesk.main:create_app --factory --no-access-log
```

This command demonstrates configuration only; it is not a production deployment
recipe. Invalid supported setting values prevent application creation. Validation
error text hides input values, but this is not a guarantee for every structured
error or logging format. Never log raw configuration or credentials.

Tests can pass an explicit `Settings` instance and an injected SQLAlchemy session
factory to `create_app(...)`. Unit tests use the `test` environment without creating
an application-owned engine; HTTP-to-PostgreSQL tests inject the guarded integration
session factory. Explicit setting values take precedence over environment variables;
tests that exercise environment loading control those variables with pytest's
`monkeypatch`.


## Continuous Integration

The `Backend CI` workflow in `.github/workflows/ci.yml` is configured to run on
pushes and pull requests. It uses an Ubuntu runner, uv 0.12.3, and the Python version
pinned in `.python-version`. Dependency installation requires the committed lockfile.
The workflow token has read-only repository-content permissions, and checkout does
not retain Git credentials for subsequent commands.

The job checks Ruff linting and formatting for src, tests, and migrations, then
runs all tests not marked integration. A failed check fails the job. PostgreSQL integration tests,
Docker builds, and deployment are outside this workflow's scope. No application
secrets or developer `.env` file are required.

Reproduce the checks locally:

```bash
uv sync --locked
uv run --locked ruff check src tests migrations
uv run --locked ruff format --check src tests migrations
uv run --locked pytest -q -m "not integration"
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
uv run alembic upgrade head
OPSDESK_RUN_INTEGRATION_TESTS=1 uv run pytest -q tests/integration
```

The password is entered at a hidden prompt, not embedded in shell history.
Unset it after the session with `unset OPSDESK_TEST_DB_PASSWORD`.
Without the explicit opt-ins, ordinary `uv run pytest -q` skips PostgreSQL data
and schema tests. Data tests use `OPSDESK_RUN_INTEGRATION_TESTS=1`; schema tests
use the separate `OPSDESK_RUN_SCHEMA_TESTS=1` flag described below. With opt-in enabled, missing/invalid configuration or a
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
  transactions. Identity scopes separately delete only `organization_memberships`,
  `users`, then `organizations`, after checking revision `6a3066cd5538`.
  Data cleanup preserves `alembic_version`; it does not reset identity sequences.
- Tests close their Sessions before cleanup. Real commits are checked from separate
  Sessions; uncommitted writes, exception cleanup, and pool return are also tested.
- Cleanup failure is surfaced and stops subsequent tests. If the body and teardown
  both fail, an `ExceptionGroup` retains both failures. Subprocess tests exercise
  failures before and after the body and prove the next test does not execute.
- A forcibly terminated process may not run teardown. The next validated scope's
  initial cleanup removes leftover rows from its reviewed allowlist. Future tables
  require Alembic migrations and an explicit cleanup-policy update.

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

The workflow now selects all non-integration tests. Hosted execution evidence must
be checked for the pushed commit; PostgreSQL CI remains #25.


## Initial Identity Schema and Migration Verification

Revision `6a3066cd5538` creates `users`, `organizations`, and
`organization_memberships`. It includes BIGINT GENERATED ALWAYS AS IDENTITY keys,
required fields, active defaults, canonical-email storage constraints, membership
pair/composite uniqueness, role validation, RESTRICT foreign keys, and the partial
unique active-owner index. The index enforces at most one active owner, not at least
one; it does not check global User activity or authorize an operation. Full email
syntax and Organization-name normalization remain application-contract concerns.

Online Alembic commands currently use only `IntegrationDatabaseSettings` and the
exact guarded product test target. This is not a development/production migration
configuration. Offline SQL generation requires no database settings or connection:

```bash
uv run alembic upgrade head --sql
```

After supplying the test settings above, apply the migration with
`uv run alembic upgrade head`. Run the schema-changing suite separately, with no
other suite using this database:

```bash
OPSDESK_RUN_SCHEMA_TESTS=1 uv run pytest -q tests/schema
```

The schema suite requires the expected database/role/server, current revision,
empty identity tables, and no unexpected public tables. It does not delete rows to
satisfy those preconditions. It downgrades to base, checks table removal, and
re-upgrades to the pinned revision. A second case injects a test failure after
removal and verifies restoration. The finally block attempts restoration; a
restoration failure stops later tests and preserves both errors when applicable.
Restoring schema does not restore deleted business data. Do not run this suite
against a populated database or interrupt it deliberately.

Only after the schema suite succeeds, run the ordinary data suite:

```bash
OPSDESK_RUN_INTEGRATION_TESTS=1 uv run pytest -q tests/integration
```

Local terminal evidence on 18 September 2026: two schema-cycle tests passed,
followed by 60 PostgreSQL data tests. Coverage includes fresh-session persistence,
cleanup on normal/exception paths, identity/unique constraints, required values,
role vocabulary, restricted deletion, and active-owner boundaries. PostgreSQL 18
RESTRICT deletion failures report `23001`; missing-parent inserts report `23503`.
These historical local results do not establish hosted PostgreSQL CI.

## User Registration

`POST /users` accepts exactly `email` and `password`. Email input is trimmed,
validated as a strict ASCII address, canonicalized to lowercase, and bounded to 254
characters. Password input is normalized with Unicode NFC, preserved without trimming,
and bounded to 15..128 code points. The server creates the User ID and active state;
registration creates no Organization, membership, or role.

The registration service hashes with Argon2id through pwdlib before persistence and
owns the commit/rollback boundary. The SQLAlchemy repository flushes before projecting
the response and maps only the named `uq_users_email` constraint to
`409 email_already_exists`. Other persistence failures remain server errors. A
successful response exposes only `user_id`, canonical `email`, and `is_active`.

Local verification on 24 September 2026: Ruff lint and format checks passed; 147
non-integration tests passed with 68 database/schema tests deselected; all 66 then-current
PostgreSQL integration tests passed. On 26 September, a controlled HTTP race used two
independent Sessions synchronized before insertion: one request returned 201, the other
returned `409 email_already_exists`, and a fresh Session found exactly one User whose
stored hash verified only the winning password. The focused registration file now has
seven passing tests. The migration-cycle suite was not rerun because this slice does
not change the schema. The final merge-candidate run passed 147 non-integration tests
with 69 database/schema tests deselected and all 67 ordinary PostgreSQL integration
tests. Hosted CI, pull-request review, and merge remain pending before issue #11 is
complete.


## Shared API Errors and Request Diagnostics

The [error/logging contract](docs/error-logging-contract.md) defines the reviewed
#3 subset implemented for #10. ApiError maps known failures to fixed public messages.
Validation errors use bounded, safe details; malformed JSON/UTF-8 maps to 400 and
unsupported or missing media type for a present JSON-request body maps to 415.
Framework 404/405 responses use the same envelope, with Allow and bearer challenges
preserved where appropriate. Other unmapped framework 4xx responses retain their
status with generic http_error. Unexpected failures before response start use a
generic 500, including unmapped database errors.

JsonAPIRoute is the factory router's default. Future separately created APIRouter
instances must also specify route_class=JsonAPIRoute for the same body policy.
Validation exposes only recognized top-level model/parameter names; deeper paths
fall back to the safe known ancestor, and unknown names to the source location.
At most 20 details are returned; Pydantic input/ctx/raw messages are not serialized.

Each HTTP request gets a server UUID in X-Request-ID and request.state.request_id.
Incoming IDs are ignored. The JSON request log contains only the server ID, bounded
method/route template, status, duration, and response-start/unexpected-error flags.
Unknown routes use <unmatched>; unknown methods use OTHER. No raw path/query/body,
Authorization value, token, exception message, or SQL URL is included.

Use --no-access-log in the Uvicorn commands above: Uvicorn's default access log can
include raw paths/query strings. Its server error logging remains enabled. Errors
after response start cannot be replaced with a new JSON response; a fixed error is
raised and the diagnostic records the original status with unexpected_error=true.
These controls do not secure arbitrary third-party loggers, proxies or debug tools.
Startup configuration validation remains separately tested before middleware exists.

Local verification on 21 September: Ruff passes, 41 files are formatted, and
101 non-integration tests pass with 62 database/schema tests deselected. An actual
Uvicorn request containing synthetic path/query/header markers returned a safe 404
and a fresh request ID; the supplied server log matched the ID, used <unmatched>,
and omitted those markers. This runtime check covered that request, not every
possible server failure. At that 21 September milestone no business endpoint or
authorization implementation was introduced. GitHub issue/PR closure remains separate
from local verification.

## Concurrency design

The accepted [transaction and locking contract](docs/concurrency-contract.md)
coordinates Organization mutations, defines ordered locks and fresh validation,
and specifies a 2-second per-lock wait with 503 concurrency_busy and no automatic
retry. This is documented design; executable locking, contention responses,
lock-wait measurement, and business concurrency tests are not implemented yet.
