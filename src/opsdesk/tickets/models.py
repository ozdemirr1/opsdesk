from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    Organization,
    OrganizationMembership,
)


@dataclass(frozen=True, slots=True)
class TicketCreationContext:
    organization: Organization
    actor_user: User | None
    actor_membership: OrganizationMembership | None


TicketPriority = Literal[
    "low",
    "medium",
    "high",
    "urgent",
]

TicketStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]


@dataclass(frozen=True, slots=True)
class NewTicket:
    organization_id: int
    requester_membership_id: int
    creator_membership_id: int
    title: str
    description: str
    priority: TicketPriority


@dataclass(frozen=True, slots=True)
class Ticket:
    ticket_id: int
    organization_id: int
    requester_membership_id: int
    creator_membership_id: int
    assignee_membership_id: int | None
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime
