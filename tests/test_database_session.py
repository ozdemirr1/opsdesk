from unittest.mock import Mock

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from opsdesk.db.session import create_session_factory, session_scope


def test_create_session_factory_produces_distinct_sessions_bound_to_engine():
    mock_engine = Mock(spec=Engine)
    factory = create_session_factory(mock_engine)

    session1 = factory()
    session2 = factory()

    try:
        assert session1 is not session2
        assert session1.bind is mock_engine
        assert session2.bind is mock_engine
    finally:
        session1.close()
        session2.close()


def test_factory_sessions_have_expire_on_commit_false():
    mock_engine = Mock(spec=Engine)
    factory = create_session_factory(mock_engine)

    session = factory()
    try:
        assert session.expire_on_commit is False
    finally:
        session.close()


def test_session_scope_closes_and_does_not_commit_on_success():
    mock_session = Mock(spec=Session)
    mock_factory = Mock(return_value=mock_session)

    with session_scope(mock_factory) as session:
        assert session is mock_session
        mock_session.close.assert_not_called()

    mock_session.close.assert_called_once()
    mock_session.commit.assert_not_called()


def test_session_scope_closes_and_propagates_exception():
    mock_session = Mock(spec=Session)
    mock_factory = Mock(return_value=mock_session)

    with pytest.raises(RuntimeError, match="Synthetic scope error"):
        with session_scope(mock_factory) as session:
            assert session is mock_session
            raise RuntimeError("Synthetic scope error")

    mock_session.close.assert_called_once()
    mock_session.commit.assert_not_called()
