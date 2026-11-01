from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from opsdesk.db.models.ticket import TicketRow
from opsdesk.db.repositories.tickets import (
    SqlAlchemyTicketRepository,
    _raise_database_error,
)
from opsdesk.tickets.models import Ticket, TicketPriority
from opsdesk.tickets.priority import TicketPriorityContext


def ticket_value(row: TicketRow) -> Ticket:
    return Ticket(**{c.name: getattr(row, c.name) for c in TicketRow.__table__.c})


class SqlAlchemyTicketPriorityRepository:
    def __init__(self, session: Session):
        self._session = session

    def lock_context(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> TicketPriorityContext | None:
        access = SqlAlchemyTicketRepository(self._session).lock_creation_context(
            actor_user_id=actor_user_id, organization_id=organization_id
        )
        if access is None:
            return None
        try:
            row = self._session.scalar(
                select(TicketRow)
                .where(
                    TicketRow.organization_id == organization_id,
                    TicketRow.ticket_id == ticket_id,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        except DBAPIError as error:
            _raise_database_error(error)
        return TicketPriorityContext(access, None if row is None else ticket_value(row))

    def set_priority(
        self, *, organization_id: int, ticket_id: int, priority: TicketPriority
    ) -> Ticket:
        # Caller owns the locks, authorization and commit. Timestamp changes atomically.
        try:
            row = self._session.execute(
                update(TicketRow)
                .where(
                    TicketRow.organization_id == organization_id,
                    TicketRow.ticket_id == ticket_id,
                )
                .values(priority=priority, updated_at=func.statement_timestamp())
                .returning(TicketRow)
                .execution_options(populate_existing=True)
            ).scalar_one()
        except DBAPIError as error:
            _raise_database_error(error)
        return ticket_value(row)
