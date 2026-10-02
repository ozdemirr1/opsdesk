from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.organizations.dependencies import (
    get_organization_creation_service,
)
from opsdesk.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationCreationResponse,
)
from opsdesk.organizations.services import (
    OrganizationActorUnavailableError,
    OrganizationCreationBusyError,
    OrganizationCreationService,
)

router = APIRouter(route_class=JsonAPIRoute)


@router.post(
    "/organizations",
    response_model=OrganizationCreationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: CreateOrganizationRequest,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    service: Annotated[
        OrganizationCreationService,
        Depends(get_organization_creation_service),
    ],
) -> OrganizationCreationResponse:
    try:
        result = service.create(
            actor_user_id=current_user.user_id,
            name=payload.name,
        )
    except OrganizationActorUnavailableError:
        raise ApiError("unauthenticated") from None
    except OrganizationCreationBusyError:
        raise ApiError("concurrency_busy") from None

    return OrganizationCreationResponse.model_validate(result)
