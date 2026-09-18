from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Identity,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsdesk.db.base import Base


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="pk_users"),
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "char_length(email) BETWEEN 1 AND 254",
            name="ck_users_email_length",
        ),
        CheckConstraint(
            """email COLLATE "C" ~ '^[!-~]+$'""",
            name="ck_users_email_ascii_nonspace",
        ),
        CheckConstraint(
            """email COLLATE "C" !~ '[A-Z]'""",
            name="ck_users_email_lowercase",
        ),
    )
