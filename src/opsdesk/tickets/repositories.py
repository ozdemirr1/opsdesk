from typing import Protocol

from opsdesk.tickets.models import (
    NewTicket,
    Ticket,
    TicketCreationContext,
)


class TicketConcurrencyError(Exception):
    pass


class TicketCreationRepository(Protocol):
    def lock_creation_context(
        self,
        *,
        organization_id: int,
        actor_user_id: int,
    ) -> TicketCreationContext | None: ...

    def create(
        self,
        new_ticket: NewTicket,
    ) -> Ticket: ...


class TicketTransaction(Protocol):
    def commit(self) -> None: ...

    def rollback(self) -> None: ...
