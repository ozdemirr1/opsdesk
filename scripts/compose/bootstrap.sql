-- Fresh isolated Compose database only. Credentials read from process environment.
\set ON_ERROR_STOP on
\set ECHO none
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
