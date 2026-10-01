from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opsdesk.organizations.normalization import normalize_organization_name

PositiveBigInt = Annotated[
    int,
    Field(ge=1, le=9_223_372_036_854_775_807),
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
