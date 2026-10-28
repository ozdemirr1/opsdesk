from dataclasses import dataclass
from datetime import datetime

from opsdesk.tickets.read_models import TicketReadAccess


@dataclass(frozen=True, slots=True)
class NewComment:
    """Trusted insertion values, after caller-owned authorization and normalization."""

    organization_id: int
    ticket_id: int
    author_membership_id: int
    content: str


@dataclass(frozen=True, slots=True)
class Comment:
    comment_id: int
    organization_id: int
    ticket_id: int
    author_membership_id: int
    content: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CommentPage:
    items: tuple[Comment, ...]
    total_count: int
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class CommentListRead:
    access: TicketReadAccess
    ticket_visible: bool
    page: CommentPage
