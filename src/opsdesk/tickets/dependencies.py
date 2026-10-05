from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.tickets import (
    SqlAlchemyTicketRepository,
    SqlAlchemyTicketTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.tickets.services import TicketCreationService


def get_ticket_creation_service(
    request: Request,
) -> Iterator[TicketCreationService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    with session_scope(factory) as session:
        yield TicketCreationService(
            repository=SqlAlchemyTicketRepository(session),
            transaction=SqlAlchemyTicketTransaction(session),
        )
