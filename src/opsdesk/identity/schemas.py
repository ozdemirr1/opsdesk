from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from opsdesk.identity.normalization import normalize_email, normalize_password

PositiveBigInt = Annotated[
    int,
    Field(ge=1, le=9_223_372_036_854_775_807),
]


class RegisterUserRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return normalize_password(value)


class UserProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    user_id: PositiveBigInt
    email: str
    is_active: bool
