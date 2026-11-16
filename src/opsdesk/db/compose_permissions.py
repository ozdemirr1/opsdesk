"""Apply reviewed runtime grants after guarded local Compose migrations."""

from sqlalchemy.exc import SQLAlchemyError

from opsdesk.db.compose import (
    ComposeMigrationSettings,
    create_compose_migration_engine,
    verify_compose_connection,
)


def main() -> None:
    engine = create_compose_migration_engine(ComposeMigrationSettings())
    try:
        with engine.begin() as connection:
            verify_compose_connection(connection)
            connection.exec_driver_sql(
                "GRANT SELECT, INSERT ON public.users, public.organizations, "
                "public.organization_memberships, public.tickets, public.comments "
                "TO opsdesk_compose_app"
            )
            # PostgreSQL row locks require UPDATE privilege on at least one column.
            for table, column in [
                ("users", "user_id"),
                ("organizations", "organization_id"),
                ("organization_memberships", "membership_id"),
            ]:
                connection.exec_driver_sql(
                    f"GRANT UPDATE ({column}) ON public.{table} TO opsdesk_compose_app"
                )
            connection.exec_driver_sql(
                "GRANT UPDATE (priority, updated_at) ON public.tickets TO opsdesk_compose_app"
            )
            for sequence in [
                "users_user_id_seq",
                "organizations_organization_id_seq",
                "organization_memberships_membership_id_seq",
                "tickets_ticket_id_seq",
                "comments_comment_id_seq",
            ]:
                connection.exec_driver_sql(
                    f"GRANT USAGE ON SEQUENCE public.{sequence} TO opsdesk_compose_app"
                )
    except SQLAlchemyError:
        raise RuntimeError("Compose permission setup failed.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
