# Docker image

The current local image builds the existing React frontend in a Node 24 stage
and copies only its dist output into the Python 3.14.7 runtime. The application
runs as UID/GID 10001. Docker build CI is implemented; Compose remains subsequent work.
No new hosted deployment is claimed.

## Docker CI — 9 November 2026

`.github/workflows/docker-ci.yml` runs on push and pull_request. Its docker-build
job checks out the repository, then runs docker build on ubuntu-latest with a
20-minute timeout and contents:read permissions. It does not publish the image,
start a container, test runtime permissions or connect to PostgreSQL. Backend
Ruff/pytest and frontend test/build/lint checks remain separate workflows.

Evidence:

- Initial build at a35af07 passed (run 42683580921).
- Controlled failure at f294911: frontend build succeeded, but Dockerfile:28
  copied from nonexistent /frontend/dist-missing and exited 1.
  [Failure log](https://github.com/ozdemirr1/opsdesk/actions/runs/42684285925).
- Restoring /frontend/dist at 67500f2 passed
  [Docker CI](https://github.com/ozdemirr1/opsdesk/actions/runs/42684862264),
  [Backend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/42684862267) and
  [Frontend CI](https://github.com/ozdemirr1/opsdesk/actions/runs/42684862697).

The branch/path-scoped ci-fundamentals.yml is a bounded exit-code demonstration,
not a product test. Its failed and recovered runs remain in Git history.
These checks establish build/test results for the cited commits, not deployment.

## Build and configuration

Run from the repository root:

```bash
docker build --progress=plain -t opsdesk:week17-multistage .
```

The image uses Python 3.14.7 and uv 0.12.3. `uv sync --locked --no-dev
--no-editable --no-cache` installs the locked runtime dependencies and application
into a Linux virtual environment. The source layout remains `src/opsdesk`.
The default command starts the Uvicorn application factory on container port 8000.
`EXPOSE 8000` does not publish a host port. Application request logs remain enabled
through the existing structured logging middleware.

The `.dockerignore` allowlist includes dependency manifests, backend source,
Alembic files and the frontend build inputs. Local node_modules, dist, environments
and credential file patterns are excluded. Frontend sources (including colocated
tests) enter the build stage; only dist is copied into the final stage.

`npm ci` uses package-lock.json. Copying manifests before frontend source lets
the dependency layer survive source-only changes. `VITE_API_BASE_URL=/` is a
public build-time value for same-origin API requests without the development
Vite proxy. Never put secrets in browser-exposed VITE variables.
`OPSDESK_FRONTEND_DIST_DIR=/app/frontend/dist` enables the existing FastAPI static
file integration. Node/npm are absent from the runtime; Python and uv remain.
The non-root process can read the root-owned application files but cannot write
into /app. No frontend feature or backend source change was introduced.
Do not copy a host virtual environment into the image or pass secrets during build.

Supply the required runtime variables described in [configuration](development.md).
The application does not automatically load `.env`, run migrations or create
tables. Starting the default command without configuration fails on the required
JWT secret. Successful image creation does not imply successful database access.

## Repeat the isolated checks

With Docker running, execute from the repository root using a host Python 3:

```bash
docker build --progress=plain -t opsdesk:week17-closure .
python3 scripts/docker/smoke.py opsdesk:week17-closure
```

The script uses unique container names, disables container networking and mounts
no host files. It supplies no production/development database credentials.
Temporary secrets are generated inside the runtime process. It verifies selected
image paths, UID/GID 10001, absence of Node/npm on PATH and denied /app write
access; the default command must reject missing JWT configuration. It then starts
Uvicorn, requests HTML and its referenced assets plus health endpoints internally,
and checks SIGTERM shutdown. Readiness 503 is expected because the loopback DB
target is deliberately unavailable. It does not exercise a real database or browser.

Containers are retained, with names printed at the start. The runtime container
is stopped in a finally block. Use docker logs with the printed runtime name to
inspect it. No removal, prune or volume operation is performed. If Docker itself
stalls, a stop can fail; inspect the named container after restoring Docker access.

On 10 November, an independent repeat passed with Engine 28.5.1, Compose
v2.40.2-desktop.1 available and 7.4 GiB free before build. Build exit 0 used cached
layers; the smoke script passed and SIGTERM completed in 0.374 seconds with exit 0.
This is an independent verification run, not a new learner exercise or cold build.

## Release boundary

The hosted preview follows main. Adding this Dockerfile can change the hosted
build path; before merging for release, review the provider start-command/port,
frontend path and migration configuration. Local smoke and Docker build CI do
not certify that hosted configuration. No provider settings or deployment were
changed during Week 17 verification.

## Multi-stage local verification — 9 November 2026

Recorded terminal checks passed:

- Image build and unchanged rebuild exited 0; npm ci, frontend build and uv sync
  reused cached layers on the unchanged rebuild.
- Configured and effective UID/GID were 10001:10001. /app writes were denied.
- Required backend/Alembic/dist paths existed; selected root exclusions,
  frontend source and node_modules were absent; node/npm were not on PATH.
- Network-disabled runtime startup ran Uvicorn as PID 1 with ephemeral secrets
  generated inside the process and an unavailable loopback database target.
- Internal HTTP checks returned 200 for /, HTML-referenced JS/CSS, favicon and
  /health/live; /health/ready returned the expected generic 503 envelope.
- Calling mount_frontend with a nonexistent path raised the expected
  "Frontend build is missing or incomplete." error, with exit 1. No file was
  deleted to trigger this failure.
- SIGTERM shutdown completed in 0.478 seconds with exit 0 and OOM false.
- Local Ruff passed; 141 files already formatted. Backend non-integration tests:
  740 passed, 286 deselected in 9.71 seconds.
- Local Node 24.21.0: frontend tests 356 passed across 17 files in 16.62 seconds;
  frontend lint and git diff whitespace checks passed.

These results do not establish browser interaction against the container,
successful database readiness/persistence, exhaustive image-layer secret scanning,
in-flight transaction draining, or remote CI. The static-file request logs used
the existing <unmatched> route label with status 200; that label alone is not 404.

## Historical single-stage verification — earlier on 9 November 2026

The following evidence refers to opsdesk:week17-basic before the multi-stage change.

The following results were recorded from local terminal runs:

| Check | Observed result |
| --- | --- |
| Basic image build | Exit 0; 31 runtime packages installed |
| Network-disabled import | Python 3.14.7; OpsDesk, FastAPI and Uvicorn import; pytest absent |
| Default command without configuration | Missing JWT secret validation; exit 1 |
| Scoped image filesystem inspection | Required source/manifests/migrations present; selected local artifacts absent |
| Isolated Uvicorn startup | PID 1; application startup complete |
| Internal `/health/live` request | 200, `{"status": "ok"}` |
| Internal `/health/ready` request with unavailable DB | 503, generic `service_unavailable` error |
| SIGTERM stop with ten-second deadline | 0.456 seconds; exit 0; OOM false; shutdown complete |
| Local Ruff lint and format check | Passed; 141 files already formatted |
| Local non-integration pytest | 740 passed, 286 deselected in 9.98 seconds |

The runtime check used `--network none`, no host port or volume, and ephemeral
JWT/database secrets generated inside the startup process. It targeted an
unavailable container-local loopback port, then used `os.execvp` to run Uvicorn
as PID 1. HTTP assertions ran inside the container using `docker exec`.
Structured request logs recorded 200 and 503 without credential values.

The filesystem check inspected selected root exclusions and source/migration
artifacts; it was not an exhaustive scan of every image layer. The regression
suite ran in the local development environment, not inside the runtime image.
No successful PostgreSQL readiness, persistence, migration, frontend build or
in-flight transaction shutdown behavior is established by these checks.
Destructive database tests remain restricted to guarded `opsdesk_product_test`.
