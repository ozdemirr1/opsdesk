from typing import Never

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from opsdesk.db.models.organization import OrganizationRow
from opsdesk.db.models.organization_membership import (
    OrganizationMembershipRow,
)
from opsdesk.db.models.ticket import TicketRow
from opsdesk.db.models.user import UserRow
from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    Organization,
    OrganizationMembership,
)
from opsdesk.tickets.models import (
    NewTicket,
    Ticket,
    TicketCreationContext,
)
from opsdesk.tickets.repositories import TicketConcurrencyError

CONCURRENCY_SQLSTATES = frozenset(
    {
        "55P03",
        "40P01",
        "40001",
    }
)

LOCK_TIMEOUT_STATEMENT = "SET LOCAL lock_timeout = '2s'"


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(
        error.orig,
        "sqlstate",
        getattr(error.orig, "pgcode", None),
    )


def _raise_database_error(error: DBAPIError) -> Never:
    if _sqlstate(error) in CONCURRENCY_SQLSTATES:
        raise TicketConcurrencyError from error

    raise error


class SqlAlchemyTicketRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_creation_context(
        self,
        *,
        organization_id: int,
        actor_user_id: int,
    ) -> TicketCreationContext | None:
        try:
            self._session.execute(text(LOCK_TIMEOUT_STATEMENT))

            organization_row = self._session.scalar(
                select(OrganizationRow)
                .where(OrganizationRow.organization_id == organization_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )

            if organization_row is None:
                return None

            user_row = self._session.scalar(
                select(UserRow)
                .where(UserRow.user_id == actor_user_id)
                .with_for_update(read=True)
                .execution_options(populate_existing=True)
            )

            membership_row = self._session.scalar(
                select(OrganizationMembershipRow)
                .where(
                    OrganizationMembershipRow.organization_id == organization_id,
                    OrganizationMembershipRow.user_id == actor_user_id,
                )
                .order_by(OrganizationMembershipRow.membership_id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        except DBAPIError as error:
            _raise_database_error(error)

        actor_user = (
            None
            if user_row is None
            else User(
                user_id=user_row.user_id,
                email=user_row.email,
                password_hash=user_row.password_hash,
                is_active=user_row.is_active,
            )
        )

        actor_membership = (
            None
            if membership_row is None
            else OrganizationMembership(
                membership_id=membership_row.membership_id,
                user_id=membership_row.user_id,
                organization_id=membership_row.organization_id,
                role=membership_row.role,
                is_active=membership_row.is_active,
            )
        )

        return TicketCreationContext(
            organization=Organization(
                organization_id=organization_row.organization_id,
                name=organization_row.name,
                is_active=organization_row.is_active,
            ),
            actor_user=actor_user,
            actor_membership=actor_membership,
        )

    def create(
        self,
        new_ticket: NewTicket,
    ) -> Ticket:
        row = TicketRow(
            organization_id=new_ticket.organization_id,
            requester_membership_id=(new_ticket.requester_membership_id),
            creator_membership_id=(new_ticket.creator_membership_id),
            assignee_membership_id=None,
            title=new_ticket.title,
            description=new_ticket.description,
            status="open",
            priority=new_ticket.priority,
        )
        self._session.add(row)

        try:
            self._session.flush()
        except DBAPIError as error:
            _raise_database_error(error)

        return Ticket(
            ticket_id=row.ticket_id,
            organization_id=row.organization_id,
            requester_membership_id=(row.requester_membership_id),
            creator_membership_id=row.creator_membership_id,
            assignee_membership_id=row.assignee_membership_id,
            title=row.title,
            description=row.description,
            status=row.status,
            priority=row.priority,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SqlAlchemyTicketTransaction:
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        try:
            self._session.commit()
        except DBAPIError as error:
            _raise_database_error(error)

    def rollback(self) -> None:
        self._session.rollback()
