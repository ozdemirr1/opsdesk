from typing import Never

from sqlalchemy import func, select, text, true
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from opsdesk.db.models.organization import OrganizationRow
from opsdesk.db.models.organization_membership import (
    OrganizationMembershipRow,
)
from opsdesk.db.models.user import UserRow
from opsdesk.identity.models import User
from opsdesk.organizations.models import (
    NewOrganization,
    NewOrganizationMembership,
    Organization,
    OrganizationList,
    OrganizationListItem,
    OrganizationMembership,
)
from opsdesk.organizations.repositories import OrganizationConcurrencyError

CONCURRENCY_SQLSTATES = frozenset(
    {
        "55P03",
        "40P01",
        "40001",
    }
)

LOCK_TIMEOUT_STATEMENT = "SET LOCAL lock_timeout = '2s'"


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(
        error.orig,
        "sqlstate",
        getattr(error.orig, "pgcode", None),
    )


def _raise_database_error(error: DBAPIError) -> Never:
    if _sqlstate(error) in CONCURRENCY_SQLSTATES:
        raise OrganizationConcurrencyError from error

    raise error


class SqlAlchemyOrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_user_for_organization_creation(
        self,
        user_id: int,
    ) -> User | None:
        try:
            self._session.execute(text(LOCK_TIMEOUT_STATEMENT))

            row = self._session.scalar(
                select(UserRow)
                .where(UserRow.user_id == user_id)
                .with_for_update(read=True)
            )
        except DBAPIError as error:
            _raise_database_error(error)

        if row is None:
            return None

        return User(
            user_id=row.user_id,
            email=row.email,
            password_hash=row.password_hash,
            is_active=row.is_active,
        )

    def create_organization(
        self,
        new_organization: NewOrganization,
    ) -> Organization:
        row = OrganizationRow(
            name=new_organization.name,
            is_active=True,
        )
        self._session.add(row)

        try:
            self._session.flush()
        except DBAPIError as error:
            _raise_database_error(error)

        return Organization(
            organization_id=row.organization_id,
            name=row.name,
            is_active=row.is_active,
        )

    def create_membership(
        self,
        new_membership: NewOrganizationMembership,
    ) -> OrganizationMembership:
        row = OrganizationMembershipRow(
            user_id=new_membership.user_id,
            organization_id=new_membership.organization_id,
            role=new_membership.role,
            is_active=True,
        )
        self._session.add(row)

        try:
            self._session.flush()
        except DBAPIError as error:
            _raise_database_error(error)

        return OrganizationMembership(
            membership_id=row.membership_id,
            user_id=row.user_id,
            organization_id=row.organization_id,
            role=row.role,
            is_active=row.is_active,
        )

    def list_for_user(
        self,
        *,
        user_id: int,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> OrganizationList:
        visible_query = (
            select(
                OrganizationRow.organization_id,
                OrganizationRow.name.label("organization_name"),
                OrganizationRow.is_active.label("organization_is_active"),
                OrganizationMembershipRow.membership_id,
                OrganizationMembershipRow.role.label("membership_role"),
                OrganizationMembershipRow.is_active.label("membership_is_active"),
            )
            .join(
                OrganizationMembershipRow,
                OrganizationMembershipRow.organization_id
                == OrganizationRow.organization_id,
            )
            .where(
                OrganizationMembershipRow.user_id == user_id,
                OrganizationMembershipRow.is_active.is_(True),
            )
        )

        if is_active is not None:
            visible_query = visible_query.where(
                OrganizationRow.is_active.is_(is_active)
            )

        visible = visible_query.cte("visible_organizations")

        page = (
            select(visible)
            .order_by(visible.c.organization_id.asc())
            .limit(limit)
            .offset(offset)
            .cte("organization_page")
        )

        total = (
            select(func.count().label("total_count"))
            .select_from(visible)
            .cte("organization_total")
        )

        statement = (
            select(
                total.c.total_count,
                page.c.organization_id,
                page.c.organization_name,
                page.c.organization_is_active,
                page.c.membership_id,
                page.c.membership_role,
                page.c.membership_is_active,
            )
            .select_from(total.outerjoin(page, true()))
            .order_by(page.c.organization_id.asc())
        )

        rows = self._session.execute(statement).mappings().all()

        items = tuple(
            OrganizationListItem(
                organization=Organization(
                    organization_id=row["organization_id"],
                    name=row["organization_name"],
                    is_active=row["organization_is_active"],
                ),
                own_membership=OrganizationMembership(
                    membership_id=row["membership_id"],
                    user_id=user_id,
                    organization_id=row["organization_id"],
                    role=row["membership_role"],
                    is_active=row["membership_is_active"],
                ),
            )
            for row in rows
            if row["organization_id"] is not None
        )

        return OrganizationList(
            items=items,
            total_count=int(rows[0]["total_count"]),
            limit=limit,
            offset=offset,
        )

    def get_for_user(
        self,
        *,
        user_id: int,
        organization_id: int,
    ) -> Organization | None:
        row = (
            self._session.execute(
                select(
                    OrganizationRow.organization_id,
                    OrganizationRow.name,
                    OrganizationRow.is_active,
                )
                .join(
                    OrganizationMembershipRow,
                    OrganizationMembershipRow.organization_id
                    == OrganizationRow.organization_id,
                )
                .where(
                    OrganizationRow.organization_id == organization_id,
                    OrganizationMembershipRow.user_id == user_id,
                    OrganizationMembershipRow.is_active.is_(True),
                )
            )
            .mappings()
            .one_or_none()
        )

        if row is None:
            return None

        return Organization(
            organization_id=row["organization_id"],
            name=row["name"],
            is_active=row["is_active"],
        )


class SqlAlchemyOrganizationTransaction:
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        try:
            self._session.commit()
        except DBAPIError as error:
            _raise_database_error(error)

    def rollback(self) -> None:
        self._session.rollback()
