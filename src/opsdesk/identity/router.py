from typing import Annotated

from fastapi import APIRouter, Depends, status

from opsdesk.api.errors import ApiError
from opsdesk.api.transport import JsonAPIRoute
from opsdesk.identity.dependencies import (
    get_current_user,
    get_login_service,
    get_registration_service,
)
from opsdesk.identity.models import User
from opsdesk.identity.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RegisterUserRequest,
    UserProfile,
)
from opsdesk.identity.services import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    LoginService,
    RegistrationService,
)

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


@router.post(
    "/auth/login",
    response_model=AccessTokenResponse,
)
def login(
    payload: LoginRequest,
    service: Annotated[
        LoginService,
        Depends(get_login_service),
    ],
) -> AccessTokenResponse:
    try:
        access_token = service.login(
            email=payload.email,
            plain_password=payload.password,
        )
    except InvalidCredentialsError:
        raise ApiError("unauthenticated") from None

    return AccessTokenResponse(
        access_token=access_token,
    )


@router.get(
    "/users/me",
    response_model=UserProfile,
)
def read_current_user(
    current_user: Annotated[
        User,
        Depends(get_current_user),
    ],
) -> UserProfile:
    return UserProfile.model_validate(current_user)
