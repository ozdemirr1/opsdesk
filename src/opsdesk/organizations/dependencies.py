from collections.abc import Iterator
from typing import Annotated

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.organizations import (
    SqlAlchemyOrganizationRepository,
    SqlAlchemyOrganizationTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.organizations.schemas import OrganizationListQuery
from opsdesk.organizations.services import (
    OrganizationCreationService,
    OrganizationReadService,
)


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


ORGANIZATION_LIST_QUERY_FIELDS = (
    "is_active",
    "limit",
    "offset",
)


def get_organization_list_query(
    request: Request,
    is_active: Annotated[str | None, Query()] = None,
    limit: Annotated[str | None, Query()] = None,
    offset: Annotated[str | None, Query()] = None,
) -> OrganizationListQuery:
    errors: list[dict[str, object]] = []

    for field_name in request.query_params:
        if field_name not in ORGANIZATION_LIST_QUERY_FIELDS:
            errors.append(
                {
                    "type": "extra_forbidden",
                    "loc": ("query",),
                    "msg": "Unexpected field.",
                    "input": None,
                }
            )

    for field_name in ORGANIZATION_LIST_QUERY_FIELDS:
        if len(request.query_params.getlist(field_name)) > 1:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ("query", field_name),
                    "msg": "Invalid value.",
                    "input": None,
                }
            )

    if errors:
        raise RequestValidationError(errors)

    raw_values = {
        key: value
        for key, value in {
            "is_active": is_active,
            "limit": limit,
            "offset": offset,
        }.items()
        if value is not None
    }

    try:
        return OrganizationListQuery.model_validate(raw_values)
    except ValidationError as error:
        prefixed_errors = []

        for validation_error in error.errors(
            include_input=False,
            include_url=False,
        ):
            prefixed_error = dict(validation_error)
            prefixed_error["loc"] = (
                "query",
                *validation_error.get("loc", ()),
            )
            prefixed_errors.append(prefixed_error)

        raise RequestValidationError(prefixed_errors) from None


def get_organization_read_service(
    request: Request,
) -> Iterator[OrganizationReadService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    with session_scope(factory) as session:
        yield OrganizationReadService(
            repository=SqlAlchemyOrganizationRepository(session),
        )
