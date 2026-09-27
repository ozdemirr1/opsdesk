from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.users import SqlAlchemyUserRepository
from opsdesk.db.session import session_scope
from opsdesk.identity.passwords import PasswordHasher
from opsdesk.identity.services import LoginService, RegistrationService
from opsdesk.identity.token_config import TokenSettings
from opsdesk.identity.tokens import AccessTokenIssuer, Clock


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


def get_login_service(
    request: Request,
) -> Iterator[LoginService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )
    token_settings: TokenSettings | None = getattr(
        request.app.state,
        "token_settings",
        None,
    )
    password_hasher: PasswordHasher | None = getattr(
        request.app.state,
        "login_password_hasher",
        None,
    )
    dummy_password_hash: str | None = getattr(
        request.app.state,
        "dummy_password_hash",
        None,
    )
    token_clock: Clock | None = getattr(
        request.app.state,
        "token_clock",
        None,
    )

    if (
        factory is None
        or token_settings is None
        or token_clock is None
        or password_hasher is None
        or dummy_password_hash is None
    ):
        raise RuntimeError("Login service is not configured.")

    with session_scope(factory) as session:
        yield LoginService(
            repository=SqlAlchemyUserRepository(session),
            password_hasher=password_hasher,
            token_issuer=AccessTokenIssuer(
                token_settings,
                clock=token_clock,
            ),
            dummy_password_hash=dummy_password_hash,
        )
