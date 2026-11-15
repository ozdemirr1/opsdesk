"""Read-only acceptance of the existing local OpsDesk Compose stack."""

import json
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = [
    "docker",
    "compose",
    "-p",
    "opsdesk-compose-dev",
    "-f",
    str(ROOT / "docker-compose.yml"),
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(*args, timeout=15):
    result = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, timeout=timeout
    )
    require(
        result.returncode == 0,
        "Command failed; raw output withheld to protect configuration.",
    )
    return result.stdout.strip()


def local_origin(binding):
    host, port = binding.rsplit(":", 1)
    require(
        host == "127.0.0.1" and port.isdecimal() and 0 < int(port) < 65536,
        "API must be published only on IPv4 loopback.",
    )
    return f"http://127.0.0.1:{int(port)}"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {"src", "href"} and value and value.startswith("/assets/"):
                require(".." not in value and "\\" not in value, "Unsafe asset path.")
                self.paths.add(value)


# Executed inside the running API, using its existing environment. Only SELECTs
# and SET TRANSACTION READ ONLY are issued; no row mutation or migration occurs.
DATABASE_CHECK = """
import os
from sqlalchemy import text
from opsdesk.db.config import DatabaseSettings
from opsdesk.db.connection import create_database_engine
assert os.getuid() == 10001 and os.getgid() == 10001
assert not os.access('/app', os.W_OK)
assert not any(key.startswith(('COMPOSE_', 'OPSDESK_COMPOSE_MIGRATION_')) for key in os.environ)
settings = DatabaseSettings()
assert (settings.host, settings.port, settings.database, settings.username) == (
    'db', 5432, 'opsdesk_compose_dev', 'opsdesk_compose_app')
engine = create_database_engine(settings)
try:
    with engine.begin() as c:
        c.execute(text('SET TRANSACTION READ ONLY'))
        assert tuple(c.execute(text('SELECT current_database(), current_user')).one()) == (
            'opsdesk_compose_dev', 'opsdesk_compose_app')
        assert not any(c.execute(text(
            'SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls '
            'FROM pg_roles WHERE rolname = current_user')).one())
        assert not c.execute(text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")).scalar_one()
        assert not c.execute(text("SELECT pg_has_role(current_user, 'opsdesk_compose_migrator', 'MEMBER')")).scalar_one()
        for table in ('users', 'organizations', 'organization_memberships', 'tickets', 'comments'):
            for privilege in ('SELECT', 'INSERT'):
                assert c.execute(text('SELECT has_table_privilege(current_user, :table, :privilege)'),
                    {'table': 'public.' + table, 'privilege': privilege}).scalar_one()
            assert not c.execute(text('SELECT has_table_privilege(current_user, :table, :privilege)'),
                {'table': 'public.' + table, 'privilege': 'DELETE'}).scalar_one()
        for privilege in ('INSERT', 'UPDATE', 'DELETE'):
            assert not c.execute(text('SELECT has_table_privilege(current_user, :table, :privilege)'),
                {'table': 'public.alembic_version', 'privilege': privilege}).scalar_one()
finally:
    engine.dispose()
print('PASS API non-root, configuration boundary and read-only runtime role checks')
"""


def main():
    command(*COMPOSE, "config", "--quiet")
    for service in ("db", "redis", "migrate", "api"):
        container = command(*COMPOSE, "ps", "-a", "-q", service)
        require(
            bool(container) and "\n" not in container,
            f"Expected one {service} container.",
        )
        state = json.loads(
            command("docker", "inspect", "--format", "{{json .State}}", container)
        )
        if service == "migrate":
            require(
                state["Status"] == "exited" and state["ExitCode"] == 0,
                "Migration has not completed successfully.",
            )
        else:
            require(state["Status"] == "running", f"{service} is not running.")
        if service == "db":
            require(
                state.get("Health", {}).get("Status") == "healthy", "DB is not healthy."
            )
        if service in {"db", "redis"}:
            ports = json.loads(
                command(
                    "docker",
                    "inspect",
                    "--format",
                    "{{json .HostConfig.PortBindings}}",
                    container,
                )
            )
            require(
                not any((ports or {}).values()),
                f"{service} must not publish host ports.",
            )
    print(
        "PASS services, completed migration, DB health and private DB/Redis ports",
        flush=True,
    )
    origin = local_origin(command(*COMPOSE, "port", "api", "8000"))
    client = build_opener(ProxyHandler({}), NoRedirect())

    def fetch(path, expected=200):
        try:
            response = client.open(origin + path, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            require(
                response.status == expected,
                f"Unexpected HTTP status for {path}: {response.status}",
            )
            return response.read()

    for attempt in range(5):
        try:
            require(
                json.loads(fetch("/health/ready")) == {"status": "ready"},
                "Unexpected readiness response.",
            )
            break
        except URLError, OSError, RuntimeError:
            if attempt == 4:
                raise RuntimeError(
                    "Readiness did not succeed within five bounded attempts."
                ) from None
            time.sleep(1)
    require(
        json.loads(fetch("/health/live")) == {"status": "ok"},
        "Unexpected liveness response.",
    )
    fetch("/users/me", 401)
    print("PASS ready/live responses and unauthenticated profile rejection", flush=True)
    html = fetch("/").decode()
    require('id="root"' in html, "React root missing.")
    assets = Assets()
    assets.feed(html)
    require(any(p.endswith(".js") for p in assets.paths), "JavaScript asset missing.")
    require(any(p.endswith(".css") for p in assets.paths), "CSS asset missing.")
    for path in sorted(assets.paths) + ["/favicon.svg"]:
        require(bool(fetch(path)), "Empty static asset.")
    print("PASS React HTML, referenced JS/CSS and favicon", flush=True)
    print(
        command(*COMPOSE, "exec", "-T", "api", "python", "-c", DATABASE_CHECK),
        flush=True,
    )
    require(
        command(*COMPOSE, "exec", "-T", "redis", "redis-cli", "PING") == "PONG",
        "Redis PING failed.",
    )
    print("PASS Redis connectivity; product cache/rate limiting is not tested")
    print("PASS local Compose acceptance; no data or container lifecycle changes")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError, ValueError, OSError, URLError, subprocess.TimeoutExpired:
        raise SystemExit(
            "FAIL Compose acceptance; check service state and bounded logs. No raw configuration printed."
        ) from None
