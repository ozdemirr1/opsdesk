from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Identity,
    Index,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsdesk.db.base import Base


class CommentRow(Base):
    __tablename__ = "comments"

    comment_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    organization_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    ticket_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_membership_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("statement_timestamp()"),
    )

    __table_args__ = (
        PrimaryKeyConstraint("comment_id", name="pk_comments"),
        CheckConstraint(
            "char_length(content) BETWEEN 1 AND 10000",
            name="ck_comments_content_length",
        ),
        ForeignKeyConstraint(
            ["organization_id", "ticket_id"],
            ["tickets.organization_id", "tickets.ticket_id"],
            name="fk_comments_ticket",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "author_membership_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
            name="fk_comments_author_membership",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_comments_ticket_chronology",
            "organization_id",
            "ticket_id",
            "created_at",
            "comment_id",
        ),
    )
