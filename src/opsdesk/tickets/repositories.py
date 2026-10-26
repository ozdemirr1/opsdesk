from typing import Protocol

from opsdesk.tickets.models import (
    NewTicket,
    Ticket,
    TicketCreationContext,
)
from opsdesk.tickets.read_models import TicketDetailRead, TicketFilters, TicketListRead


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


class TicketReadRepository(Protocol):
    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        filters: TicketFilters,
        limit: int,
        offset: int,
    ) -> TicketListRead: ...

    def get_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        ticket_id: int,
    ) -> TicketDetailRead: ...
