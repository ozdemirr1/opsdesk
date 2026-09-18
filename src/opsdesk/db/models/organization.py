from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Identity,
    PrimaryKeyConstraint,
    Text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from opsdesk.db.base import Base


class OrganizationRow(Base):
    __tablename__ = "organizations"

    organization_id: Mapped[int] = mapped_column(
        BigInteger, Identity(always=True), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=true(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("organization_id", name="pk_organizations"),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 255",
            name="ck_organizations_name_length",
        ),
    )
