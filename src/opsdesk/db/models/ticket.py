from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsdesk.db.base import Base


class TicketRow(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    organization_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    requester_membership_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    creator_membership_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    assignee_membership_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'open'"),
    )
    priority: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'medium'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "ticket_id",
            name="pk_tickets",
        ),
        UniqueConstraint(
            "organization_id",
            "ticket_id",
            name="uq_tickets_org_ticket",
        ),
        CheckConstraint(
            "char_length(title) BETWEEN 1 AND 255",
            name="ck_tickets_title_length",
        ),
        CheckConstraint(
            "char_length(description) BETWEEN 1 AND 10000",
            name="ck_tickets_description_length",
        ),
        CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'closed')",
            name="ck_tickets_status",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'urgent')",
            name="ck_tickets_priority",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.organization_id"],
            name="fk_tickets_organization_id",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "requester_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
            name="fk_tickets_requester_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "creator_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
            name="fk_tickets_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "assignee_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
            name="fk_tickets_assignee_membership",
            ondelete="RESTRICT",
            match="SIMPLE",
        ),
    )
