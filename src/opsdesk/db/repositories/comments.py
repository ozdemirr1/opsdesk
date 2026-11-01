from sqlalchemy import and_, func, select, true
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from opsdesk.comments.models import (
    Comment,
    CommentCreationContext,
    CommentListRead,
    CommentPage,
    NewComment,
)
from opsdesk.db.models.comment import CommentRow
from opsdesk.db.models.ticket import TicketRow
from opsdesk.db.repositories.ticket_visibility import (
    access_statement,
    visible_statement,
)
from opsdesk.db.repositories.tickets import (
    SqlAlchemyTicketRepository,
    _raise_database_error,
)
from opsdesk.tickets.models import Ticket
from opsdesk.tickets.read_models import TicketReadAccess


def _comment(row) -> Comment:
    return Comment(
        **{column.name: row[column.name] for column in CommentRow.__table__.c}
    )


class SqlAlchemyCommentRepository:
    """No commit, edit or delete operations. The service owns the transaction.

    create() is a low-level primitive, not an authorization boundary: its caller
    must lock/recheck the actor, membership, Organization and Ticket, derive the
    author and validate posting state/content before insertion. CommentService owns this sequence.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_creation_context(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> CommentCreationContext | None:
        # Same connection and transaction: Organization -> User -> membership -> Ticket.
        access = SqlAlchemyTicketRepository(self._session).lock_creation_context(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
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
        ticket = (
            None
            if row is None
            else Ticket(
                **{
                    column.name: getattr(row, column.name)
                    for column in TicketRow.__table__.c
                }
            )
        )
        return CommentCreationContext(access=access, ticket=ticket)

    def create(self, new_comment: NewComment) -> Comment:
        row = CommentRow(
            organization_id=new_comment.organization_id,
            ticket_id=new_comment.ticket_id,
            author_membership_id=new_comment.author_membership_id,
            content=new_comment.content,
        )
        self._session.add(row)
        try:
            self._session.flush()
        except DBAPIError as error:
            _raise_database_error(error)
        return Comment(
            comment_id=row.comment_id,
            organization_id=row.organization_id,
            ticket_id=row.ticket_id,
            author_membership_id=row.author_membership_id,
            content=row.content,
            created_at=row.created_at,
        )

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        ticket_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> CommentListRead:
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(offset) is not int
            or offset < 0
        ):
            raise ValueError("Invalid comment pagination.")
        access = access_statement(actor_user_id, organization_id)
        parent = visible_statement(actor_user_id, organization_id).cte("comment_parent")
        parent = (
            select(parent)
            .where(parent.c.ticket_id == ticket_id)
            .cte("visible_comment_parent")
        )
        visible = (
            select(*CommentRow.__table__.c)
            .join(
                parent,
                and_(
                    parent.c.organization_id == CommentRow.organization_id,
                    parent.c.ticket_id == CommentRow.ticket_id,
                ),
            )
            .cte("visible_comments")
        )
        page = (
            select(visible)
            .order_by(visible.c.created_at, visible.c.comment_id)
            .limit(limit)
            .offset(offset)
            .cte("comment_page")
        )
        total = (
            select(func.count().label("total_count"))
            .select_from(visible)
            .cte("comment_total")
        )
        statement = (
            select(
                access,
                select(parent.c.ticket_id).exists().label("ticket_visible"),
                total.c.total_count,
                page,
            )
            .select_from(access.join(total, true()).outerjoin(page, true()))
            .order_by(page.c.created_at, page.c.comment_id)
        )
        try:
            rows = self._session.execute(statement).mappings().all()
        except DBAPIError as error:
            _raise_database_error(error)
        first = rows[0]
        return CommentListRead(
            access=TicketReadAccess(
                actor_active=first["actor_active"],
                membership_active=first["membership_active"],
                organization_active=first["organization_active"],
            ),
            ticket_visible=first["ticket_visible"],
            page=CommentPage(
                items=tuple(
                    _comment(row) for row in rows if row["comment_id"] is not None
                ),
                total_count=int(first["total_count"]),
                limit=limit,
                offset=offset,
            ),
        )
