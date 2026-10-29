from opsdesk.comments.models import Comment, CommentPage, NewComment
from opsdesk.comments.normalization import normalize_comment_content
from opsdesk.comments.repositories import CommentRepository
from opsdesk.tickets.repositories import TicketConcurrencyError, TicketTransaction
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)


class CommentClosedError(Exception):
    pass


class CommentBusyError(Exception):
    pass


class CommentContentError(Exception):
    pass


class CommentService:
    def __init__(self, repository: CommentRepository, transaction: TicketTransaction):
        self._repository = repository
        self._transaction = transaction

    def create(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int, content: str
    ) -> Comment:
        try:
            try:
                content = normalize_comment_content(content)
            except ValueError:
                raise CommentContentError from None
            context = self._repository.lock_creation_context(
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
                member.role not in {"agent", "admin", "owner"}
                and ticket.requester_membership_id != member.membership_id
            ):
                raise TicketNotFoundError
            if ticket.status == "closed":
                raise CommentClosedError
            comment = self._repository.create(
                NewComment(
                    organization_id=access.organization.organization_id,
                    ticket_id=ticket.ticket_id,
                    author_membership_id=member.membership_id,
                    content=content,
                )
            )
            self._transaction.commit()
            return comment
        except TicketConcurrencyError:
            self._transaction.rollback()
            raise CommentBusyError from None
        except Exception:
            self._transaction.rollback()
            raise

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        ticket_id: int,
        limit: int,
        offset: int,
    ) -> CommentPage:
        try:
            result = self._repository.list_for_actor(
                actor_user_id=actor_user_id,
                organization_id=organization_id,
                ticket_id=ticket_id,
                limit=limit,
                offset=offset,
            )
        except TicketConcurrencyError:
            self._transaction.rollback()
            raise CommentBusyError from None
        if not result.access.actor_active:
            raise TicketActorUnavailableError
        if not result.access.membership_active:
            raise TicketOrganizationAccessDeniedError
        if not result.access.organization_active:
            raise TicketOrganizationSuspendedError
        if not result.ticket_visible:
            raise TicketNotFoundError
        return result.page
