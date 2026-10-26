from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from opsdesk.tickets.models import TicketPriority, TicketStatus
from opsdesk.tickets.normalization import FORBIDDEN_TITLE_CHARACTERS
from opsdesk.tickets.read_models import TicketFilters
from opsdesk.tickets.schemas import TicketResponse

BIGINT_MAX = 9_223_372_036_854_775_807


def parse_query_integer(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("Invalid integer query value.")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        # Bound conversion before int(); arbitrary leading zeroes remain valid.
        significant = value.lstrip("0") or "0"
        if len(significant) <= 19:
            return int(significant)
    raise ValueError("Invalid integer query value.")


QueryInteger = Annotated[int, BeforeValidator(parse_query_integer)]


class TicketListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)

    q: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignment: Literal["assigned", "unassigned"] | None = None
    assignee_membership_id: (
        Annotated[QueryInteger, Field(ge=1, le=BIGINT_MAX)] | None
    ) = None
    limit: Annotated[QueryInteger, Field(ge=1, le=100)] = 20
    offset: Annotated[QueryInteger, Field(ge=0, le=BIGINT_MAX)] = 0

    @field_validator("q")
    @classmethod
    def normalize_search(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) > 255 or any(c in value for c in FORBIDDEN_TITLE_CHARACTERS):
            raise ValueError("Invalid title search.")
        return value.strip() or None

    @model_validator(mode="after")
    def check_assignment(self) -> "TicketListQuery":
        if self.assignment == "unassigned" and self.assignee_membership_id is not None:
            raise ValueError("Conflicting assignment filters.")
        return self

    def to_filters(self) -> TicketFilters:
        return TicketFilters(
            q=self.q,
            status=self.status,
            priority=self.priority,
            assignment=self.assignment,
            assignee_membership_id=self.assignee_membership_id,
        )


class TicketListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)

    items: tuple[TicketResponse, ...]
    total_count: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0, le=BIGINT_MAX)]
