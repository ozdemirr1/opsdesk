#!/bin/sh
# Invoked only by the official PostgreSQL entrypoint for an empty local volume.
set -eu
: "${COMPOSE_MIGRATOR_PASSWORD:?Missing migration password}"
: "${COMPOSE_APP_PASSWORD:?Missing application password}"
[ "$POSTGRES_DB" = opsdesk_compose_dev ] && [ "$POSTGRES_USER" = postgres ] || exit 1
# Suppress SQL error echoes: CREATE ROLE statements contain credentials.
if ! psql -X --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 >/dev/null 2>&1 <<'SQL'
SET log_statement = none;
SET log_min_error_statement = panic;
SET log_min_duration_statement = -1;
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'opsdesk_compose_dev' OR current_user <> 'postgres'
    OR inet_server_addr() IS NOT NULL THEN
   RAISE EXCEPTION 'Unexpected bootstrap connection';
 END IF;
END $$;
\getenv migration_password COMPOSE_MIGRATOR_PASSWORD
\getenv app_password COMPOSE_APP_PASSWORD
SELECT format('CREATE ROLE opsdesk_compose_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', :'migration_password') \gexec
SELECT format('CREATE ROLE opsdesk_compose_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', :'app_password') \gexec
REVOKE ALL ON DATABASE opsdesk_compose_dev FROM PUBLIC;
GRANT CONNECT ON DATABASE opsdesk_compose_dev TO opsdesk_compose_migrator, opsdesk_compose_app;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO opsdesk_compose_migrator;
GRANT USAGE ON SCHEMA public TO opsdesk_compose_app;
COMMIT;
SQL
then
 echo 'Compose role bootstrap failed; inspect the dedicated volume without deleting it.' >&2
 exit 1
fi
echo 'Compose roles initialized.'
