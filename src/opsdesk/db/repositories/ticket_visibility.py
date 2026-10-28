"""Shared parent-Ticket visibility for Ticket and Comment reads."""

from sqlalchemy import and_, or_, select

from opsdesk.db.models.organization import OrganizationRow
from opsdesk.db.models.organization_membership import OrganizationMembershipRow
from opsdesk.db.models.ticket import TicketRow
from opsdesk.db.models.user import UserRow


def access_statement(actor_user_id: int, organization_id: int):
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


def visible_statement(actor_user_id: int, organization_id: int):
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
