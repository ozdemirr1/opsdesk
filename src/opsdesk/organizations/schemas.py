from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)

from opsdesk.organizations.normalization import normalize_organization_name

PositiveBigInt = Annotated[
    int,
    Field(ge=1, le=9_223_372_036_854_775_807),
]


def parse_exact_query_boolean(value: object) -> bool:
    if value == "true":
        return True

    if value == "false":
        return False

    raise ValueError("Invalid boolean query value.")


def parse_query_integer(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid integer query value.")

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)

    raise ValueError("Invalid integer query value.")


ExactQueryBoolean = Annotated[
    bool,
    BeforeValidator(parse_exact_query_boolean),
]

PaginationLimit = Annotated[
    int,
    BeforeValidator(parse_query_integer),
    Field(ge=1, le=100),
]

PaginationOffset = Annotated[
    int,
    BeforeValidator(parse_query_integer),
    Field(ge=0),
]


class CreateOrganizationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_organization_name(value)


class OrganizationProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    organization_id: PositiveBigInt
    name: str
    is_active: bool


class OrganizationMembershipProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    membership_id: PositiveBigInt
    organization_id: PositiveBigInt
    role: Literal["owner", "admin", "agent", "customer"]
    is_active: bool


class OrganizationCreationResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    organization: OrganizationProfile
    own_membership: OrganizationMembershipProfile


class OrganizationListQuery(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    is_active: ExactQueryBoolean | None = None
    limit: PaginationLimit = 20
    offset: PaginationOffset = 0


class OrganizationListItemResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    organization: OrganizationProfile
    own_membership: OrganizationMembershipProfile


class OrganizationListResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    items: tuple[OrganizationListItemResponse, ...]
    total_count: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0)]
