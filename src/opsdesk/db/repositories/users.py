from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from opsdesk.db.models.user import UserRow
from opsdesk.identity.models import NewUser, User
from opsdesk.identity.repositories import UserEmailConflictError

EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, new_user: NewUser) -> User:
        row = UserRow(
            email=new_user.email,
            password_hash=new_user.password_hash,
            is_active=True,
        )
        self._session.add(row)

        try:
            self._session.flush()
        except IntegrityError as error:
            if _constraint_name(error) == EMAIL_UNIQUE_CONSTRAINT:
                raise UserEmailConflictError from error
            raise

        return User(
            user_id=row.user_id,
            email=row.email,
            password_hash=row.password_hash,
            is_active=row.is_active,
        )
