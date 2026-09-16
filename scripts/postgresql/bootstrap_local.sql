-- One-time local PostgreSQL provisioning for the standalone OpsDesk project.
-- Run with psql, connected to postgres as a local administrator.
-- Do not use --single-transaction: CREATE DATABASE cannot run in a transaction.
-- Passwords are deliberately absent. Set them interactively with \password.
-- Existing product targets cause an early failure; no objects are reset/dropped.
-- The Month 02 opsdesk_dev and opsdesk_test databases are never modified.
\set ON_ERROR_STOP on

DO $$
BEGIN
    IF current_database() <> 'postgres' THEN
        RAISE EXCEPTION 'Run local provisioning from the postgres database.';
    END IF;

    IF inet_server_addr() IS DISTINCT FROM inet '127.0.0.1'
       OR inet_server_port() IS DISTINCT FROM 5432 THEN
        RAISE EXCEPTION 'Unexpected local PostgreSQL server target.';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname IN ('opsdesk_product_app', 'opsdesk_product_test_runner')
    ) OR EXISTS (
        SELECT 1 FROM pg_database
        WHERE datname IN ('opsdesk_product_dev', 'opsdesk_product_test')
    ) THEN
        RAISE EXCEPTION 'Product roles/databases already exist; inspect the setup instead of rerunning bootstrap.';
    END IF;
END;
$$;

CREATE ROLE opsdesk_product_app
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE ROLE opsdesk_product_test_runner
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE DATABASE opsdesk_product_dev
    OWNER opsdesk_product_app
    TEMPLATE template0;

CREATE DATABASE opsdesk_product_test
    OWNER opsdesk_product_test_runner
    TEMPLATE template0;

REVOKE ALL ON DATABASE opsdesk_product_dev FROM PUBLIC;
REVOKE ALL ON DATABASE opsdesk_product_test FROM PUBLIC;
