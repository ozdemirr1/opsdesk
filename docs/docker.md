# Basic backend Docker image

This single-stage image is the first Month 05 local backend milestone. It does
not yet include the existing React build, a non-root runtime, Compose or a
Docker build CI job. It is not a replacement for the published full-stack release.

## Build and configuration

Run from the repository root:

```bash
docker build --progress=plain -t opsdesk:week17-basic .
```

The image uses Python 3.14.7 and uv 0.12.3. `uv sync --locked --no-dev
--no-editable --no-cache` installs the locked runtime dependencies and application
into a Linux virtual environment. The source layout remains `src/opsdesk`.
The default command starts the Uvicorn application factory on container port 8000.
`EXPOSE 8000` does not publish a host port. Application request logs remain enabled
through the existing structured logging middleware.

The `.dockerignore` allowlist includes dependency manifests, source and Alembic
files. Local environments, credentials, frontend sources and tests are excluded.
Do not copy a host virtual environment into the image or pass secrets during build.

Supply the required runtime variables described in [configuration](development.md).
The application does not automatically load `.env`, run migrations or create
tables. Starting the default command without configuration fails on the required
JWT secret. Successful image creation does not imply successful database access.

## Local verification — 9 November 2026

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
