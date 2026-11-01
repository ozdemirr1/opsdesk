from typing import Protocol

from opsdesk.comments.models import (
    Comment,
    CommentCreationContext,
    CommentListRead,
    NewComment,
)


class CommentRepository(Protocol):
    def lock_creation_context(
        self, *, actor_user_id: int, organization_id: int, ticket_id: int
    ) -> CommentCreationContext | None: ...

    def create(self, new_comment: NewComment) -> Comment: ...

    def list_for_actor(
        self,
        *,
        actor_user_id: int,
        organization_id: int,
        ticket_id: int,
        limit: int,
        offset: int,
    ) -> CommentListRead: ...
