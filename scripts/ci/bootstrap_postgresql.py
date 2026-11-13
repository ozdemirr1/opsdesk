"""Provision only a fresh GitHub-hosted PostgreSQL service; never a local DB."""

import os
import secrets
import subprocess
import sys
from pathlib import Path


def docker(*args, input=None):
    result = subprocess.run(
        ["docker", *args], input=input, text=True, capture_output=True, timeout=30
    )
    if result.returncode:
        raise SystemExit("CI PostgreSQL bootstrap failed; sensitive output withheld.")
    return result.stdout


def main():
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"
    ):
        raise SystemExit("Bootstrap requires a disposable GitHub-hosted runner.")
    service = sys.argv[1]
    password = secrets.token_hex(32)
    print(f"::add-mask::{password}", flush=True)
    # Existing objects fail rather than being reset. No development DB is created.
    sql = f"""
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SET log_min_duration_statement = -1;
CREATE ROLE opsdesk_product_test_runner LOGIN PASSWORD '{password}'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE DATABASE opsdesk_product_test OWNER opsdesk_product_test_runner TEMPLATE template0;
REVOKE ALL ON DATABASE opsdesk_product_test FROM PUBLIC;
"""
    docker(
        "exec",
        "-i",
        service,
        "psql",
        "-X",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        input=sql,
    )
    # Replace initial CI-only trust with password-authenticated loopback access.
    # No host port is published. Reject TCP connections through the bridge.
    docker(
        "exec",
        "--user",
        "postgres",
        service,
        "sh",
        "-eu",
        "-c",
        "printf '%s\n' 'local all all trust' 'host all all 127.0.0.1/32 scram-sha-256' 'host all all ::1/128 scram-sha-256' 'host all all all reject' > \"$PGDATA/pg_hba.conf\"",
    )
    docker(
        "exec",
        service,
        "psql",
        "-X",
        "-U",
        "postgres",
        "-d",
        "postgres",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        "SELECT pg_reload_conf();",
    )
    path = Path(os.environ["RUNNER_TEMP"]) / "opsdesk-test.env"
    with path.open("x", opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
        handle.write(
            "OPSDESK_TEST_DB_HOST=127.0.0.1\n"
            "OPSDESK_TEST_DB_PORT=5432\n"
            "OPSDESK_TEST_DB_DATABASE=opsdesk_product_test\n"
            "OPSDESK_TEST_DB_USERNAME=opsdesk_product_test_runner\n"
            f"OPSDESK_TEST_DB_PASSWORD={password}\n"
        )
    print("Fresh test database provisioned; loopback SCRAM authentication enabled.")


if __name__ == "__main__":
    main()
