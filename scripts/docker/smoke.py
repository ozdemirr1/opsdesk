"""Repeat the isolated Docker checks without real database access or deletion."""

import argparse
import json
import subprocess
import time
import uuid


def docker(*args, expected=0, timeout=30):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != expected:
        raise RuntimeError(
            f"Docker {args[0]} returned {result.returncode}, expected {expected}"
        )
    return result.stdout


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("image", help="Locally built image tag or ID")
parser.add_argument(
    "--railway",
    action="store_true",
    help="Check the proposed Railway start command on port 8080 and offline migrations",
)
args = parser.parse_args()
prefix = f"opsdesk-smoke-{uuid.uuid4().hex[:8]}"
runtime = f"{prefix}-runtime"
names = [f"{prefix}-audit", f"{prefix}-config", runtime]
print("Retained container names:", ", ".join(names), flush=True)

audit = """
import os, shutil
from pathlib import Path
root = Path('/app')
assert (os.getuid(), os.getgid()) == (10001, 10001)
for name in ['frontend/dist/index.html', 'frontend/dist/favicon.svg',
             'frontend/dist/assets', 'src/opsdesk/main.py', 'alembic.ini', 'migrations']:
    assert (root / name).exists(), name
for name in ['.env', '.git', 'tests', 'frontend/src', 'frontend/node_modules']:
    assert not (root / name).exists(), name
assert shutil.which('node') is None
assert shutil.which('npm') is None
assert not os.access(root, os.W_OK)
print('PASS image paths, non-root and application directory permissions')
"""
print(
    docker(
        "run",
        "--pull=never",
        "--name",
        names[0],
        "--network",
        "none",
        args.image,
        "python",
        "-c",
        audit,
    ).strip(),
    flush=True,
)

docker(
    "run",
    "--pull=never",
    "--name",
    names[1],
    "--network",
    "none",
    args.image,
    expected=1,
)
config_state = json.loads(docker("inspect", "--format", "{{json .State}}", names[1]))
assert config_state["ExitCode"] == 1
config_logs = subprocess.run(
    ["docker", "logs", names[1]], capture_output=True, text=True, timeout=10
)
assert config_logs.returncode == 0
assert "TokenSettings" in config_logs.stdout + config_logs.stderr
assert "Field required" in config_logs.stdout + config_logs.stderr
print("PASS default command rejects missing configuration", flush=True)

launch = """
import os, secrets
os.environ.update({
    'OPSDESK_ENVIRONMENT': 'development',
    'OPSDESK_JWT_SECRET': secrets.token_urlsafe(32),
    'OPSDESK_DB_HOST': '127.0.0.1',
    'OPSDESK_DB_PORT': '65432',
    'OPSDESK_DB_DATABASE': 'unavailable_smoke_target',
    'OPSDESK_DB_USERNAME': 'smoke_placeholder',
    'OPSDESK_DB_PASSWORD': secrets.token_urlsafe(32),
    'OPSDESK_DB_CONNECT_TIMEOUT_SECONDS': '2',
})
os.execvp('uvicorn', ['uvicorn', 'opsdesk.main:create_app', '--factory',
                     '--host', '0.0.0.0', '--port', '8000', '--no-access-log'])
"""
if args.railway:
    launch = (
        launch[: launch.index("os.execvp(")]
        + """
os.environ['PORT'] = '8080'
os.execv('/bin/sh', ['/bin/sh', '-c',
    'exec /app/.venv/bin/uvicorn opsdesk.main:create_app --factory '
    '--host 0.0.0.0 --port "${PORT:-8080}" --no-access-log'])
"""
    )
    sql = docker(
        "run",
        "--pull=never",
        "--network",
        "none",
        "--name",
        f"{prefix}-migration",
        args.image,
        "/app/.venv/bin/alembic",
        "-x",
        "target=hosted",
        "upgrade",
        "head",
        "--sql",
    )
    assert "84c2f9a17d60" in sql and "COMMIT;" in sql
    print(
        "PASS offline migration SQL; no database contacted; retained:",
        f"{prefix}-migration",
        flush=True,
    )

http_check = """
import json, time
from html.parser import HTMLParser
from urllib.request import urlopen
from urllib.error import HTTPError, URLError

def fetch(path, expected):
    try:
        response = urlopen('http://127.0.0.1:8000' + path, timeout=3)
    except HTTPError as exc:
        response = exc
    with response:
        assert response.status == expected, (path, response.status)
        body = response.read()
    print(path, expected)
    return body

for attempt in range(20):
    try:
        assert json.loads(fetch('/health/live', 200)) == {'status': 'ok'}
        break
    except URLError:
        if attempt == 19:
            raise
        time.sleep(0.25)

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'src', 'href'} and value and value.startswith('/assets/'):
                self.paths.add(value)

html = fetch('/', 200).decode()
assert 'id="root"' in html
assets = Assets()
assets.feed(html)
assert any(p.endswith('.js') for p in assets.paths)
assert any(p.endswith('.css') for p in assets.paths)
for path in sorted(assets.paths):
    assert fetch(path, 200)
assert fetch('/favicon.svg', 200)
assert json.loads(fetch('/health/ready', 503))['error']['code'] == 'service_unavailable'
"""
if args.railway:
    http_check = http_check.replace("127.0.0.1:8000", "127.0.0.1:8080")

try:
    docker(
        "run",
        "-d",
        "--pull=never",
        "--name",
        runtime,
        "--network",
        "none",
        args.image,
        "python",
        "-c",
        launch,
    )
    print(docker("exec", runtime, "python", "-c", http_check).strip(), flush=True)
finally:
    # Stop only our uniquely named container. Never remove containers or volumes.
    started = time.monotonic()
    docker("stop", "--timeout", "10", runtime, timeout=20)
    print(f"Stop elapsed: {time.monotonic() - started:.3f}s", flush=True)

state = json.loads(docker("inspect", "--format", "{{json .State}}", runtime))
assert state["Status"] == "exited" and state["ExitCode"] == 0
assert not state["OOMKilled"]
logs = subprocess.run(
    ["docker", "logs", runtime], capture_output=True, text=True, timeout=10
)
assert logs.returncode == 0
assert "Application shutdown complete." in logs.stdout + logs.stderr
print("PASS SIGTERM shutdown; all smoke checks passed; containers retained")
