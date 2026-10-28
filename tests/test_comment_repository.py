from unittest.mock import Mock

import pytest

from opsdesk.db.repositories.comments import SqlAlchemyCommentRepository


@pytest.mark.parametrize(
    "limit,offset", [(0, 0), (101, 0), (True, 0), (20, -1), (20, False), (20, "0")]
)
def test_comment_repository_rejects_invalid_pagination_before_database(limit, offset):
    session = Mock()
    with pytest.raises(ValueError, match="Invalid comment pagination"):
        SqlAlchemyCommentRepository(session).list_for_actor(
            actor_user_id=1, organization_id=1, ticket_id=1, limit=limit, offset=offset
        )
    session.execute.assert_not_called()
