from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import get_registration_service
from opsdesk.identity.schemas import RegisterUserRequest, UserProfile
from opsdesk.identity.services import EmailAlreadyExistsError, RegistrationService

router = APIRouter(route_class=JsonAPIRoute)


@router.post(
    "/users",
    response_model=UserProfile,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterUserRequest,
    service: Annotated[
        RegistrationService,
        Depends(get_registration_service),
    ],
) -> UserProfile:
    try:
        user = service.register_user(
            email=payload.email,
            plain_password=payload.password,
        )
    except EmailAlreadyExistsError:
        raise ApiError("email_already_exists") from None

    return UserProfile.model_validate(user)
