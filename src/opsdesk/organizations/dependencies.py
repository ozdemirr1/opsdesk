from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.organizations import (
    SqlAlchemyOrganizationRepository,
    SqlAlchemyOrganizationTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.organizations.services import OrganizationCreationService


def get_organization_creation_service(
    request: Request,
) -> Iterator[OrganizationCreationService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    with session_scope(factory) as session:
        repository = SqlAlchemyOrganizationRepository(session)

        yield OrganizationCreationService(
            repository=repository,
            transaction=SqlAlchemyOrganizationTransaction(session),
        )
