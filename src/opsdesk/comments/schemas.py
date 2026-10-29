from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from opsdesk.comments.normalization import normalize_comment_content
from opsdesk.tickets.read_schemas import BIGINT_MAX, QueryInteger
from opsdesk.tickets.schemas import PositiveBigInt


class CreateCommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return normalize_comment_content(value)


class CommentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)
    comment_id: PositiveBigInt
    author_membership_id: PositiveBigInt
    content: str
    created_at: AwareDatetime


class CommentListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    limit: Annotated[QueryInteger, Field(ge=1, le=100)] = 20
    offset: Annotated[QueryInteger, Field(ge=0, le=BIGINT_MAX)] = 0


class CommentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)
    items: tuple[CommentResponse, ...]
    total_count: Annotated[int, Field(ge=0)]
    limit: Annotated[int, Field(ge=1, le=100)]
    offset: Annotated[int, Field(ge=0, le=BIGINT_MAX)]
