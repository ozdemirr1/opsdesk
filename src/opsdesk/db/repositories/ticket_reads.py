from collections.abc import Mapping

from sqlalchemy import and_, func, or_, select, true
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from opsdesk.db.models.organization import OrganizationRow
from opsdesk.db.models.organization_membership import OrganizationMembershipRow
from opsdesk.db.models.ticket import TicketRow
from opsdesk.db.models.user import UserRow
from opsdesk.db.repositories.tickets import _raise_database_error
from opsdesk.tickets.models import Ticket
from opsdesk.tickets.read_models import (
    TicketDetailRead,
    TicketFilters,
    TicketList,
    TicketListRead,
    TicketReadAccess,
)


def _access_statement(actor_user_id: int, organization_id: int):
    # This one-row CTE and the visible rows use the same statement snapshot.
    return select(
        select(UserRow.user_id)
        .where(UserRow.user_id == actor_user_id, UserRow.is_active.is_(True))
        .exists()
        .label("actor_active"),
        select(OrganizationMembershipRow.membership_id)
        .where(
            OrganizationMembershipRow.user_id == actor_user_id,
            OrganizationMembershipRow.organization_id == organization_id,
            OrganizationMembershipRow.is_active.is_(True),
        )
        .exists()
        .label("membership_active"),
        select(OrganizationRow.organization_id)
        .where(
            OrganizationRow.organization_id == organization_id,
            OrganizationRow.is_active.is_(True),
        )
        .exists()
        .label("organization_active"),
    ).cte("ticket_read_access")


def _visible_statement(actor_user_id: int, organization_id: int):
    membership = OrganizationMembershipRow
    return (
        select(*TicketRow.__table__.c)
        .join(
            OrganizationRow,
            OrganizationRow.organization_id == TicketRow.organization_id,
        )
        .join(membership, membership.organization_id == TicketRow.organization_id)
        .join(UserRow, UserRow.user_id == membership.user_id)
        .where(
            TicketRow.organization_id == organization_id,
            UserRow.user_id == actor_user_id,
            UserRow.is_active.is_(True),
            membership.is_active.is_(True),
            OrganizationRow.is_active.is_(True),
            or_(
                membership.role.in_(("agent", "admin", "owner")),
                and_(
                    membership.role == "customer",
                    TicketRow.requester_membership_id == membership.membership_id,
                ),
            ),
        )
    )


def _filtered_statement(statement, filters: TicketFilters):
    if filters.q is not None:
        literal = filters.q.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        statement = statement.where(TicketRow.title.ilike(f"%{literal}%", escape="!"))
    if filters.status is not None:
        statement = statement.where(TicketRow.status == filters.status)
    if filters.priority is not None:
        statement = statement.where(TicketRow.priority == filters.priority)
    if filters.assignment == "assigned":
        statement = statement.where(TicketRow.assignee_membership_id.is_not(None))
    elif filters.assignment == "unassigned":
        statement = statement.where(TicketRow.assignee_membership_id.is_(None))
    if filters.assignee_membership_id is not None:
        statement = statement.where(
            TicketRow.assignee_membership_id == filters.assignee_membership_id
        )
    return statement


def _access(row: Mapping) -> TicketReadAccess:
    return TicketReadAccess(
        actor_active=row["actor_active"],
        membership_active=row["membership_active"],
        organization_active=row["organization_active"],
    )


def _ticket(row: Mapping) -> Ticket:
    return Ticket(**{column.name: row[column.name] for column in TicketRow.__table__.c})


class SqlAlchemyTicketReadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        filters: TicketFilters,
        limit: int,
        offset: int,
    ) -> TicketListRead:
        access = _access_statement(actor_user_id, organization_id)
        visible = _filtered_statement(
            _visible_statement(actor_user_id, organization_id), filters
        ).cte("visible_tickets")
        page = (
            select(visible)
            .order_by(visible.c.created_at.desc(), visible.c.ticket_id.desc())
            .limit(limit)
            .offset(offset)
            .cte("ticket_page")
        )
        total = (
            select(func.count().label("total_count")).select_from(visible).cte("total")
        )
        statement = (
            select(access, total.c.total_count, page)
            .select_from(access.join(total, true()).outerjoin(page, true()))
            .order_by(page.c.created_at.desc(), page.c.ticket_id.desc())
        )
        try:
            rows = self._session.execute(statement).mappings().all()
        except DBAPIError as error:
            _raise_database_error(error)
        return TicketListRead(
            access=_access(rows[0]),
            page=TicketList(
                items=tuple(
                    _ticket(row) for row in rows if row["ticket_id"] is not None
                ),
                total_count=int(rows[0]["total_count"]),
                limit=limit,
                offset=offset,
            ),
        )

    def get_for_actor(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> TicketDetailRead:
        access = _access_statement(actor_user_id, organization_id)
        visible = (
            _visible_statement(actor_user_id, organization_id)
            .where(TicketRow.ticket_id == ticket_id)
            .cte("visible_ticket")
        )
        statement = select(access, visible).select_from(
            access.outerjoin(visible, true())
        )
        try:
            row = self._session.execute(statement).mappings().one()
        except DBAPIError as error:
            _raise_database_error(error)
        return TicketDetailRead(
            access=_access(row),
            ticket=None if row["ticket_id"] is None else _ticket(row),
        )
