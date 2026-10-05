from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import get_current_user
from opsdesk.identity.models import User
from opsdesk.organizations.dependencies import (
    get_organization_creation_service,
    get_organization_list_query,
    get_organization_read_service,
)
from opsdesk.organizations.schemas import (
    CreateOrganizationRequest,
    OrganizationCreationResponse,
    OrganizationListQuery,
    OrganizationListResponse,
    OrganizationProfile,
    PositiveBigInt,
)
from opsdesk.organizations.services import (
    OrganizationAccessDeniedError,
    OrganizationActorUnavailableError,
    OrganizationCreationBusyError,
    OrganizationCreationService,
    OrganizationReadService,
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


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
)
def list_organizations(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    query: Annotated[
        OrganizationListQuery,
        Depends(get_organization_list_query),
    ],
    service: Annotated[
        OrganizationReadService,
        Depends(get_organization_read_service),
    ],
) -> OrganizationListResponse:
    result = service.list_for_actor(
        actor_user_id=current_user.user_id,
        is_active=query.is_active,
        limit=query.limit,
        offset=query.offset,
    )

    return OrganizationListResponse.model_validate(result)


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationProfile,
)
def read_organization(
    organization_id: PositiveBigInt,
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
    service: Annotated[
        OrganizationReadService,
        Depends(get_organization_read_service),
    ],
) -> OrganizationProfile:
    try:
        organization = service.get_for_actor(
            actor_user_id=current_user.user_id,
            organization_id=organization_id,
        )
    except OrganizationAccessDeniedError:
        raise ApiError("organization_access_denied") from None

    return OrganizationProfile.model_validate(organization)
