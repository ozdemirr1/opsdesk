from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.tickets.dependencies import (
    get_ticket_creation_service,
    get_ticket_list_query,
    get_ticket_read_service,
    reject_ticket_detail_query,
)
from opsdesk.tickets.read_schemas import TicketListQuery, TicketListResponse
from opsdesk.tickets.schemas import (
    CreateTicketRequest,
    PositiveBigInt,
    TicketResponse,
)
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketCreationBusyError,
    TicketCreationService,
    TicketNotFoundError,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
    TicketReadBusyError,
    TicketReadService,
)

router = APIRouter(route_class=JsonAPIRoute)


@router.post(
    "/organizations/{organization_id}/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ticket(
    organization_id: PositiveBigInt,
    payload: CreateTicketRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    service: Annotated[
        TicketCreationService,
        Depends(get_ticket_creation_service),
    ],
) -> TicketResponse:
    try:
        ticket = service.create(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
        )
    except TicketActorUnavailableError:
        raise ApiError("unauthenticated") from None
    except TicketOrganizationAccessDeniedError:
        raise ApiError("organization_access_denied") from None
    except TicketOrganizationSuspendedError:
        raise ApiError("organization_suspended") from None
    except TicketCreationBusyError:
        raise ApiError("concurrency_busy") from None

    return TicketResponse.model_validate(ticket)


@router.get(
    "/organizations/{organization_id}/tickets",
    response_model=TicketListResponse,
)
def list_tickets(
    organization_id: PositiveBigInt,
    current_user: Annotated[User, Depends(get_current_user)],
    query: Annotated[TicketListQuery, Depends(get_ticket_list_query)],
    service: Annotated[TicketReadService, Depends(get_ticket_read_service)],
) -> TicketListResponse:
    try:
        result = service.list_for_actor(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
            filters=query.to_filters(),
            limit=query.limit,
            offset=query.offset,
        )
    except TicketActorUnavailableError:
        raise ApiError("unauthenticated") from None
    except TicketOrganizationAccessDeniedError:
        raise ApiError("organization_access_denied") from None
    except TicketOrganizationSuspendedError:
        raise ApiError("organization_suspended") from None
    except TicketReadBusyError:
        raise ApiError("concurrency_busy") from None
    return TicketListResponse.model_validate(result)


@router.get(
    "/organizations/{organization_id}/tickets/{ticket_id}",
    response_model=TicketResponse,
)
def read_ticket(
    organization_id: PositiveBigInt,
    ticket_id: PositiveBigInt,
    current_user: Annotated[User, Depends(get_current_user)],
    query_check: Annotated[None, Depends(reject_ticket_detail_query)],
    service: Annotated[TicketReadService, Depends(get_ticket_read_service)],
) -> TicketResponse:
    try:
        result = service.get_for_actor(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
            ticket_id=ticket_id,
        )
    except TicketActorUnavailableError:
        raise ApiError("unauthenticated") from None
    except TicketOrganizationAccessDeniedError:
        raise ApiError("organization_access_denied") from None
    except TicketOrganizationSuspendedError:
        raise ApiError("organization_suspended") from None
    except TicketNotFoundError:
        raise ApiError("ticket_not_found") from None
    except TicketReadBusyError:
        raise ApiError("concurrency_busy") from None
    return TicketResponse.model_validate(result)
