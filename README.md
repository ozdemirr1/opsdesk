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
Business endpoints, authentication, and database persistence are not implemented.
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
