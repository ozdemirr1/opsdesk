from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.comments.dependencies import get_comment_list_query, get_comment_service
from opsdesk.comments.schemas import (
    CommentListQuery,
    CommentListResponse,
    CommentResponse,
    CreateCommentRequest,
)
from opsdesk.comments.services import (
    CommentBusyError,
    CommentClosedError,
    CommentContentError,
    CommentService,
)
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.tickets.schemas import PositiveBigInt
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
)

router = APIRouter(route_class=JsonAPIRoute)
PATH = "/organizations/{organization_id}/tickets/{ticket_id}/comments"


@contextmanager
def comment_errors():
    try:
        yield
    except TicketActorUnavailableError:
        raise ApiError("unauthenticated") from None
    except TicketOrganizationAccessDeniedError:
        raise ApiError("organization_access_denied") from None
    except TicketOrganizationSuspendedError:
        raise ApiError("organization_suspended") from None
    except TicketNotFoundError:
        raise ApiError("ticket_not_found") from None
    except CommentClosedError:
        raise ApiError("state_conflict") from None
    except CommentContentError:
        raise ApiError("validation_error") from None
    except CommentBusyError:
        raise ApiError("concurrency_busy") from None


@router.post(PATH, response_model=CommentResponse, status_code=201)
def create_comment(
    organization_id: PositiveBigInt,
    ticket_id: PositiveBigInt,
    payload: CreateCommentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentResponse:
    with comment_errors():
        result = service.create(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
            ticket_id=ticket_id,
            content=payload.content,
        )
    return CommentResponse.model_validate(result)


@router.get(PATH, response_model=CommentListResponse)
def list_comments(
    organization_id: PositiveBigInt,
    ticket_id: PositiveBigInt,
    current_user: Annotated[User, Depends(get_current_user)],
    query: Annotated[CommentListQuery, Depends(get_comment_list_query)],
    service: Annotated[CommentService, Depends(get_comment_service)],
) -> CommentListResponse:
    with comment_errors():
        result = service.list_for_actor(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
            ticket_id=ticket_id,
            limit=query.limit,
            offset=query.offset,
        )
    return CommentListResponse.model_validate(result)
