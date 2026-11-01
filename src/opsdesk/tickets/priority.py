from dataclasses import dataclass
from typing import Protocol

from opsdesk.tickets.models import Ticket, TicketCreationContext, TicketPriority
from opsdesk.tickets.repositories import TicketConcurrencyError, TicketTransaction
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)


@dataclass(frozen=True, slots=True)
class TicketPriorityContext:
    access: TicketCreationContext
    ticket: Ticket | None


class TicketPriorityRepository(Protocol):
    def lock_context(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> TicketPriorityContext | None: ...
    def set_priority(
        self, *, organization_id: int, ticket_id: int, priority: TicketPriority
    ) -> Ticket: ...


class PriorityPermissionError(Exception):
    pass


class PriorityStateError(Exception):
    pass


class PriorityBusyError(Exception):
    pass


class PriorityInputError(Exception):
    pass


class TicketPriorityService:
    def __init__(
        self, repository: TicketPriorityRepository, transaction: TicketTransaction
    ):
        self._repository = repository
        self._transaction = transaction

    def change(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        ticket_id: int,
        priority: TicketPriority,
    ) -> Ticket:
        try:
            if not isinstance(priority, str) or priority not in (
                "low",
                "medium",
                "high",
                "urgent",
            ):
                raise PriorityInputError
            context = self._repository.lock_context(
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                ticket_id=ticket_id,
            )
            if context is None:
                raise TicketOrganizationAccessDeniedError
            access = context.access
            if access.actor_user is None or not access.actor_user.is_active:
                raise TicketActorUnavailableError
            member = access.actor_membership
            if member is None or not member.is_active:
                raise TicketOrganizationAccessDeniedError
            if not access.organization.is_active:
                raise TicketOrganizationSuspendedError
            ticket = context.ticket
            if ticket is None or (
                member.role == "customer"
                and ticket.requester_membership_id != member.membership_id
            ):
                raise TicketNotFoundError
            if member.role not in ("agent", "admin", "owner"):
                raise PriorityPermissionError
            if ticket.status not in ("open", "in_progress"):
                raise PriorityStateError
            # No-op is decided only after fresh scope, role and state checks.
            if ticket.priority != priority:
                ticket = self._repository.set_priority(
                    organization_id=organization_id,
                    ticket_id=ticket_id,
                    priority=priority,
                )
            self._transaction.commit()
            return ticket
        except TicketConcurrencyError:
            self._transaction.rollback()
            raise PriorityBusyError from None
        except Exception:
            self._transaction.rollback()
            raise
