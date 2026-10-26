from collections.abc import Iterator
from typing import Annotated

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from opsdesk.db.repositories.ticket_reads import SqlAlchemyTicketReadRepository
from opsdesk.db.repositories.tickets import (
    SqlAlchemyTicketRepository,
    SqlAlchemyTicketTransaction,
)
from opsdesk.db.session import session_scope
from opsdesk.tickets.read_schemas import TicketListQuery
from opsdesk.tickets.services import TicketCreationService, TicketReadService


def get_ticket_creation_service(
    request: Request,
) -> Iterator[TicketCreationService]:
    factory: sessionmaker[Session] | None = getattr(
        request.app.state,
        "session_factory",
        None,
    )

    if factory is None:
        raise RuntimeError("Database session factory is not configured.")

    with session_scope(factory) as session:
        yield TicketCreationService(
            repository=SqlAlchemyTicketRepository(session),
            transaction=SqlAlchemyTicketTransaction(session),
        )


def get_ticket_read_service(request: Request) -> Iterator[TicketReadService]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise RuntimeError("Database session factory is not configured.")
    with session_scope(factory) as session:
        yield TicketReadService(repository=SqlAlchemyTicketReadRepository(session))


def reject_ticket_detail_query(request: Request) -> None:
    if request.query_params:
        raise RequestValidationError(
            [
                {
                    "type": "extra_forbidden",
                    "loc": ("query",),
                    "msg": "Unexpected field.",
                    "input": None,
                }
            ]
        )


def get_ticket_list_query(
    request: Request,
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    assignment: Annotated[str | None, Query()] = None,
    assignee_membership_id: Annotated[str | None, Query()] = None,
    limit: Annotated[str | None, Query()] = None,
    offset: Annotated[str | None, Query()] = None,
) -> TicketListQuery:
    values = {
        "q": q,
        "status": status,
        "priority": priority,
        "assignment": assignment,
        "assignee_membership_id": assignee_membership_id,
        "limit": limit,
        "offset": offset,
    }
    errors = []
    for key in request.query_params:
        if key not in values:
            errors.append(
                {
                    "type": "extra_forbidden",
                    "loc": ("query",),
                    "msg": "Unexpected field.",
                    "input": None,
                }
            )
        elif len(request.query_params.getlist(key)) > 1:
            errors.append(
                {
                    "type": "value_error",
                    "loc": ("query", key),
                    "msg": "Invalid value.",
                    "input": None,
                }
            )
    if errors:
        raise RequestValidationError(errors)
    try:
        return TicketListQuery.model_validate(
            {key: value for key, value in values.items() if value is not None}
        )
    except ValidationError as error:
        # Do not retain submitted values, exception contexts or untrusted key names.
        details = [
            {
                "type": item["type"],
                "loc": ("query", *item["loc"]),
                "msg": "Invalid value.",
                "input": None,
            }
            for item in error.errors(
                include_input=False, include_url=False, include_context=False
            )
        ]
        raise RequestValidationError(details) from None
