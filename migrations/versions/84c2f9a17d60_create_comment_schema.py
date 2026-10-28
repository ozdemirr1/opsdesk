"""Create tenant-consistent append-only comment storage.

Revision ID: 84c2f9a17d60
Revises: 31be9023cfb2
"""

import sqlalchemy as sa
from alembic import op

revision = "84c2f9a17d60"
down_revision = "31be9023cfb2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column(
            "comment_id", sa.BigInteger(), sa.Identity(always=True), nullable=False
        ),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.BigInteger(), nullable=False),
        sa.Column("author_membership_id", sa.BigInteger(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("statement_timestamp()"),
        ),
        sa.PrimaryKeyConstraint("comment_id", name="pk_comments"),
        sa.CheckConstraint(
            "char_length(content) BETWEEN 1 AND 10000",
            name="ck_comments_content_length",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "ticket_id"],
            ["tickets.organization_id", "tickets.ticket_id"],
            name="fk_comments_ticket",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "author_membership_id"],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
            name="fk_comments_author_membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_comments_ticket_chronology",
        "comments",
        ["organization_id", "ticket_id", "created_at", "comment_id"],
    )


def downgrade() -> None:
    # Explicitly destructive: only exercise on the guarded test target.
    op.drop_index("ix_comments_ticket_chronology", table_name="comments")
    op.drop_table("comments")
