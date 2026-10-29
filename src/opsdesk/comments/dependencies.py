from collections.abc import Iterator
from typing import Annotated

from fastapi import Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from opsdesk.comments.schemas import CommentListQuery
from opsdesk.comments.services import CommentService
from opsdesk.db.repositories.comments import SqlAlchemyCommentRepository
from opsdesk.db.repositories.tickets import SqlAlchemyTicketTransaction
from opsdesk.db.session import session_scope


def get_comment_service(request: Request) -> Iterator[CommentService]:
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise RuntimeError("Database session factory is not configured.")
    with session_scope(factory) as session:
        yield CommentService(
            SqlAlchemyCommentRepository(session), SqlAlchemyTicketTransaction(session)
        )


def get_comment_list_query(
    request: Request,
    limit: Annotated[str | None, Query()] = None,
    offset: Annotated[str | None, Query()] = None,
) -> CommentListQuery:
    values = {
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
        return CommentListQuery.model_validate(
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
