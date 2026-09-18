from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsdesk.db.base import Base


class OrganizationMembershipRow(Base):
    __tablename__ = "organization_memberships"

    membership_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "users.user_id",
            name="fk_memberships_user_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "organizations.organization_id",
            name="fk_memberships_organization_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("membership_id", name="pk_organization_memberships"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'agent', 'customer')",
            name="ck_memberships_role",
        ),
        UniqueConstraint(
            "user_id",
            "organization_id",
            name="uq_memberships_user_org",
        ),
        UniqueConstraint(
            "organization_id",
            "membership_id",
            name="uq_memberships_org_membership",
        ),
        Index(
            "uq_memberships_active_owner_per_org",
            "organization_id",
            unique=True,
            postgresql_where=text("role = 'owner' AND is_active = true"),
        ),
    )
