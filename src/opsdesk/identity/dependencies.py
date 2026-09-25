from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.users import SqlAlchemyUserRepository
from opsdesk.db.session import session_scope
from opsdesk.identity.passwords import PasswordHasher
from opsdesk.identity.services import RegistrationService


def get_registration_service(
    request: Request,
) -> Iterator[RegistrationService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    with session_scope(factory) as session:
        yield RegistrationService(
            repository=SqlAlchemyUserRepository(session),
            transaction=session,
            password_hasher=PasswordHasher(),
        )
