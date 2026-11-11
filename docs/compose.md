# Local Compose development

## Verified 11 November 2026

The local stack now includes isolated role bootstrap and a one-shot migration
service. API starts only after migration and runtime grants succeed. PostgreSQL
health is checked over TCP, so its temporary socket-only init server is not enough.
The separate compose migration target accepts only db:5432 / opsdesk_compose_dev /
opsdesk_compose_migrator and verifies connected identity and unprivileged role
attributes. Existing test/development/hosted guards are unchanged.

Runtime grants are explicit: SELECT/INSERT on the five current business tables,
USAGE on their identity sequences, UPDATE(priority, updated_at) on tickets and
single-column UPDATE on user/org/membership IDs to permit existing row locks.
PostgreSQL row-lock privilege requirements mean those latter grants also authorize
updates to those columns; application authorization remains necessary. Runtime has
no schema CREATE, DELETE, migration-role membership or alembic_version write grant.
There are no blanket future-table grants. New features need a permission review.

## Run and inspect

Prepare four independent local random values in an ignored mode-600 .env, using
.env.example as the field reference. Never overwrite an existing .env or reuse
hosted credentials. Bootstrap passwords apply only to an empty volume; changing
.env does not rotate passwords already stored in PostgreSQL.

```bash
docker compose config --quiet
docker compose build api
docker compose up -d --no-build --no-recreate
docker compose ps -a
docker compose logs --tail 15 migrate
curl --fail --silent --show-error http://127.0.0.1:8089/health/ready
```

Open http://127.0.0.1:8089 for the existing UI. Stop with docker compose stop.
No down/prune/removal is part of this workflow. --no-recreate preserves existing
containers; it also means changed definitions/mounts are not applied to them.
A future replacement must be explicitly reviewed before removing any container.

The api profile from the early skeleton was removed after migration gating was
implemented. Redis is connectivity-only, internal, ephemeral and not used by the
application yet. API has no bootstrap/migration secret. Migration has no admin or
JWT secret. Startup dependencies do not provide continuous health supervision.

## Evidence and recovery boundary

- Focused migration/guard tests: 100 passed. Full non-DB backend regression:
  773 passed / 286 deselected. Additional permission-module tests: 3 passed.
- First init attempt hit a bind-mounted shell bad-interpreter permission error;
  the volume was retained, role absence checked, and bootstrap completed explicitly.
  scripts/compose/bootstrap.sh is retained as the recovery helper, not auto-mounted.
- Default init now mounts bootstrap.sql, avoiding shell execution. A second fresh
  project/volume completed init -> healthy DB -> migration exit 0 -> API startup
  without manual intervention. Its readiness returned 200; it was stopped/retained.
- Primary project: liveness/readiness and root HTML 200; synthetic registration
  201, login/profile/list 200 and organization creation 201. Rows were retained.
  Redis PING returned PONG. No full browser or Ticket/Comment flow is claimed.
- Runtime SQL checks verified identity and absence of DDL/DELETE/migration-table
  write/migration-role membership. Generated secret values were absent from
  captured logs of both projects.
- Separate network-disabled rejection project used the wrong DB target and no DB
  service. Migration exited 1; dependent API remained Created, never started.
- No destructive integration test, database reset or deletion was performed.

Retained primary project opsdesk-compose-dev uses loopback 8089. The stopped fresh
project is opsdesk-compose-fresh-20261111 (8090); failed dependency proof project
is opsdesk-migration-reject-c59ded. The primary DB still has the original shell
mount because no container was recreated; future fresh starts use the SQL mount.

Downloaded images: postgres:18.6-bookworm digest
sha256:f1ea2a1a4fb7b68d4836be1fdcb8a6466a89b072158bf9d97663600538c294c5;
redis:8.2.11-bookworm digest
sha256:b0b01167ff47bc3868e56a967895a26be4230891a1f42a78ab61cdd227accc8d.
These are observed pull digests; YAML currently pins patch tags, not immutable
repository digests. Existing React build and Dockerfile behavior were preserved.

Still pending: delayed DB and bounded retry exercises, restart persistence,
backup/restore, guarded PostgreSQL CI and full Week 18 acceptance. Destructive
checks remain confined to opsdesk_product_test; this Compose DB is never that target.

# Earlier configuration-only checkpoint

## 11 November 2026 — configuration skeleton only

The first exercise proved service DNS (`web:8000`) works without published host
ports; client-local `127.0.0.1:8000` correctly refused the connection. This product
skeleton maps that model to API, PostgreSQL and Redis. It has not been started.

| Service | Address | Responsibility |
| --- | --- | --- |
| api | Mac loopback 8089 to container 8000 | Existing React dist and FastAPI |
| db | db:5432 on internal data network | Separate opsdesk_compose_dev database |
| redis | redis:6379 on internal data network | Connectivity foundation only |

Only API joins the default network as well as the internal data network. DB and
Redis have no published host ports. No existing external network/volume is reused.
The project name is opsdesk-compose-dev and the project-scoped named volume is
postgres_data. PostgreSQL 18 uses /var/lib/postgresql/18/docker below the volume
mounted at /var/lib/postgresql. Redis storage is ephemeral tmpfs, with persistence
disabled; no product caching, limiter or queue is implemented.

The API uses an application-role name but that role does not exist yet. PostgreSQL
bootstrap management uses the postgres role; its password is not passed to API.
Migration role creation, grants, the separate guarded compose migration target,
one-shot migration service and startup conditions remain the next exercise.
Do not run up yet. API is behind the application profile to avoid suggesting that
the default service set already provides a working application. A profile is an
opt-in selector, not a readiness or security guard.

## Configuration review

.env.example contains empty secret fields and is safe to track. A future local
.env is ignored by Git. Compose reads it for interpolation; only explicitly listed
environment keys enter each service. Do not use a wholesale env_file injection
that would pass every secret to API. Existing local env files must not be replaced.
Required `${VAR:?message}` expressions reject both missing and empty values.
Even disabled profiles may require interpolation values during config parsing.

For a controlled missing-config experiment (no service creation):

```bash
env -u COMPOSE_POSTGRES_PASSWORD -u COMPOSE_APP_PASSWORD -u COMPOSE_JWT_SECRET   docker compose --env-file /dev/null --profile application config --quiet
```

Expected: nonzero exit naming a required variable. With local values prepared in
the later runtime step, use `docker compose --profile application config --quiet`.
Do not paste a full rendered config: it contains resolved secrets.

This skeleton is not acceptance evidence. Do not run destructive tests against
opsdesk_compose_dev. Existing guarded opsdesk_product_test checks remain unchanged.
Normal session stop uses docker compose stop. Removal, including down/down -v,
requires separate approval. No removal is part of this exercise.

Before first startup: confirm free disk space; verify image manifests/digests;
implement and test role/bootstrap/migration gating; provision unique local secrets;
then demonstrate cold start and readiness. Image patch tags were checked against
the official image catalog; image pulls and architecture/runtime validation are
not claimed at this checkpoint.

Sources: [PostgreSQL image data layout](https://github.com/docker-library/docs/blob/master/postgres/README.md#pgdata),
[Compose networking](https://docs.docker.com/compose/how-tos/networking/).
