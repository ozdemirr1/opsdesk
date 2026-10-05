from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.tickets.dependencies import (
    get_ticket_creation_service,
)
from opsdesk.tickets.schemas import (
    CreateTicketRequest,
    PositiveBigInt,
    TicketResponse,
)
from opsdesk.tickets.services import (
    TicketActorUnavailableError,
    TicketCreationBusyError,
    TicketCreationService,
    TicketOrganizationAccessDeniedError,
    TicketOrganizationSuspendedError,
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
