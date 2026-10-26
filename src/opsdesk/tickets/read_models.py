from dataclasses import dataclass
from typing import Literal

from opsdesk.tickets.models import Ticket, TicketPriority, TicketStatus


@dataclass(frozen=True, slots=True)
class TicketReadAccess:
    actor_active: bool
    membership_active: bool
    organization_active: bool


@dataclass(frozen=True, slots=True)
class TicketFilters:
    q: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignment: Literal["assigned", "unassigned"] | None = None
    assignee_membership_id: int | None = None


@dataclass(frozen=True, slots=True)
class TicketList:
    items: tuple[Ticket, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class TicketListRead:
    access: TicketReadAccess
    page: TicketList


@dataclass(frozen=True, slots=True)
class TicketDetailRead:
    access: TicketReadAccess
    ticket: Ticket | None
