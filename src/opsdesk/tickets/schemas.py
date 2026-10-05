from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from opsdesk.tickets.normalization import (
    normalize_ticket_description,
    normalize_ticket_title,
)

PositiveBigInt = Annotated[
    int,
    Field(ge=1, le=9_223_372_036_854_775_807),
]

TicketPriority = Literal[
    "low",
    "medium",
    "high",
    "urgent",
]

TicketStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "closed",
]


class CreateTicketRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        hide_input_in_errors=True,
    )

    title: str
    description: str
    priority: TicketPriority = "medium"

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return normalize_ticket_title(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return normalize_ticket_description(value)


class TicketResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        from_attributes=True,
    )

    ticket_id: PositiveBigInt
    organization_id: PositiveBigInt
    requester_membership_id: PositiveBigInt
    creator_membership_id: PositiveBigInt
    assignee_membership_id: PositiveBigInt | None
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    created_at: AwareDatetime
    updated_at: AwareDatetime
