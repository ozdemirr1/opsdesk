from concurrent.futures import ThreadPoolExecutor
from queue import Queue

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from tests.integration import test_comments
from tests.integration.test_comments import insert, read
from tests.integration.test_ticket_creation import (
    bearer_headers,
    build_app,
    wait_for_database_blocker,
)

from opsdesk.comments.services import (
    CommentBusyError,
    CommentClosedError,
    CommentService,
)
from opsdesk.db.models import (
    CommentRow,
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.repositories.comments import SqlAlchemyCommentRepository
from opsdesk.db.repositories.tickets import SqlAlchemyTicketTransaction
from opsdesk.db.session import session_scope

pytestmark = pytest.mark.integration
context = test_comments.context


def path(data, i=0, org=None):
    org = data["orgs"][0] if org is None else org
    return f"/organizations/{org}/tickets/{data['tickets'][i]}/comments"


def service(session, transaction=None):
    return CommentService(
        SqlAlchemyCommentRepository(session),
        transaction or SqlAlchemyTicketTransaction(session),
    )


def args(data, i=0):
    return dict(
        actor_user_id=data["users"][i],
        organization_id=data["orgs"][0 if i < 2 else 1],
        ticket_id=data["tickets"][i],
        content="New comment",
    )


def count(factory):
    with session_scope(factory) as session:
        return session.scalar(select(func.count()).select_from(CommentRow))


@pytest.mark.parametrize("role", ["customer", "agent", "admin", "owner"])
@pytest.mark.parametrize("status", ["open", "in_progress", "resolved", "closed"])
def test_post_role_state_and_get_closed_history(context, role, status):
    factory, data = context
    insert(factory, data, content="Existing history")
    target = 0 if role == "customer" else 1
    with session_scope(factory) as session:
        session.execute(
            update(OrganizationMembershipRow)
            .where(OrganizationMembershipRow.membership_id == data["members"][0])
            .values(role=role)
        )
        session.execute(
            update(TicketRow)
            .where(TicketRow.ticket_id == data["tickets"][target])
            .values(status=status)
        )
        session.commit()
        before = session.get(TicketRow, data["tickets"][target]).updated_at
    with TestClient(build_app(factory)) as client:
        headers = bearer_headers(data["users"][0])
        response = client.post(
            path(data, target),
            json={"content": "  First\r\nSecond\tline  "},
            headers=headers,
        )
        assert response.status_code == (409 if status == "closed" else 201)
        if status != "closed":
            assert response.json()["author_membership_id"] == data["members"][0]
            assert response.json()["content"] == "First\nSecond\tline"
        first = client.get(path(data) + "?limit=1&offset=0", headers=headers)
        assert first.status_code == 200
        assert first.json()["items"][0]["content"] == "Existing history"
        beyond = client.get(path(data) + "?offset=100", headers=headers)
        assert beyond.json()["items"] == []
        assert beyond.json()["total_count"] == first.json()["total_count"]
    assert count(factory) == (1 if status == "closed" else 2)
    with session_scope(factory) as session:
        ticket = session.get(TicketRow, data["tickets"][target])
        assert ticket.updated_at == before and ticket.status == status


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "target,foreign_org,status", [(1, False, 404), (2, False, 404), (2, True, 403)]
)
def test_hidden_and_foreign_parent_access(context, method, target, foreign_org, status):
    factory, data = context
    insert(factory, data, target, content="Private tenant content")
    with TestClient(build_app(factory)) as client:
        response = client.request(
            method,
            path(data, target, data["orgs"][1] if foreign_org else None),
            headers=bearer_headers(data["users"][0]),
            **({"json": {"content": "x"}} if method == "post" else {}),
        )
        assert response.status_code == status
        assert "Private tenant content" not in response.text
    assert count(factory) == 1


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "inactive,status", [("user", 401), ("membership", 403), ("organization", 403)]
)
def test_inactive_context_denied(context, method, inactive, status):
    factory, data = context
    model, column, value = {
        "user": (UserRow, UserRow.user_id, data["users"][0]),
        "membership": (
            OrganizationMembershipRow,
            OrganizationMembershipRow.membership_id,
            data["members"][0],
        ),
        "organization": (
            OrganizationRow,
            OrganizationRow.organization_id,
            data["orgs"][0],
        ),
    }[inactive]
    with session_scope(factory) as session:
        session.execute(update(model).where(column == value).values(is_active=False))
        session.commit()
    with TestClient(build_app(factory)) as client:
        response = client.request(
            method,
            path(data),
            headers=bearer_headers(data["users"][0]),
            **({"json": {"content": "x"}} if method == "post" else {}),
        )
        assert response.status_code == status
    assert count(factory) == 0


def test_real_api_empty_missing_invalid_and_chronological_pages(context):
    factory, data = context
    with TestClient(build_app(factory)) as client:
        headers = bearer_headers(data["users"][0])
        assert client.get(path(data), headers=headers).json() == dict(
            items=[], total_count=0, limit=20, offset=0
        )
        assert (
            client.get(
                f"/organizations/{data['orgs'][0]}/tickets/9223372036854775807/comments",
                headers=headers,
            ).status_code
            == 404
        )
        assert (
            client.post(
                path(data), json={"content": "\x00private"}, headers=headers
            ).status_code
            == 422
        )
        ids = [
            client.post(
                path(data), json={"content": f"Entry {i}"}, headers=headers
            ).json()["comment_id"]
            for i in range(3)
        ]
        pages = [
            client.get(path(data) + f"?limit=1&offset={i}", headers=headers).json()
            for i in range(3)
        ]
        assert [page["items"][0]["comment_id"] for page in pages] == ids
        assert all(page["total_count"] == 3 for page in pages)
    assert count(factory) == 3


def test_commit_failure_rolls_back_flushed_comment(context):
    factory, data = context
    with session_scope(factory) as session:

        class FailingCommit(SqlAlchemyTicketTransaction):
            def commit(self):
                assert session.scalar(select(func.count()).select_from(CommentRow)) == 1
                raise RuntimeError("Synthetic commit failure")

        with pytest.raises(RuntimeError, match="Synthetic commit failure"):
            service(session, FailingCommit(session)).create(**args(data))
        assert not session.in_transaction()
    assert count(factory) == 0


@pytest.mark.parametrize("comment_first", [False, True])
def test_comment_and_cooperating_close_serialized_in_both_orders(
    context, comment_first
):
    # No status endpoint exists yet: closure deliberately follows its lock contract.
    factory, data = context
    pids = Queue()
    with session_scope(factory) as first:
        first_pid = first.scalar(text("SELECT pg_backend_pid()"))
        SqlAlchemyCommentRepository(first).lock_creation_context(
            **{k: v for k, v in args(data).items() if k != "content"}
        )
        if not comment_first:
            first.execute(
                update(TicketRow)
                .where(TicketRow.ticket_id == data["tickets"][0])
                .values(status="closed")
            )

        def worker():
            with session_scope(factory) as session:
                # Retain a stale ORM object to verify populate_existing after waiting.
                stale = session.get(TicketRow, data["tickets"][0])
                assert stale.status == "open"
                pids.put(session.scalar(text("SELECT pg_backend_pid()")))
                if not comment_first:
                    with pytest.raises(CommentClosedError):
                        service(session).create(**args(data))
                    return
                locked = SqlAlchemyCommentRepository(session).lock_creation_context(
                    **{k: v for k, v in args(data).items() if k != "content"}
                )
                assert locked.ticket.status == "open"
                session.execute(
                    update(TicketRow)
                    .where(TicketRow.ticket_id == data["tickets"][0])
                    .values(status="closed")
                )
                session.commit()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker)
            try:
                wait_for_database_blocker(
                    factory,
                    worker_pid=pids.get(timeout=5),
                    expected_blocker_pid=first_pid,
                )
                if comment_first:
                    service(first).create(**args(data))
                else:
                    first.commit()
            finally:
                first.rollback()
            future.result(timeout=10)
    assert count(factory) == int(comment_first)
    with session_scope(factory) as session:
        assert session.get(TicketRow, data["tickets"][0]).status == "closed"
    assert read(factory, data).ticket_visible


def test_lock_timeout_rolls_back_while_other_organization_progresses(context):
    factory, data = context
    pids = Queue()
    with session_scope(factory) as blocker:
        blocker_pid = blocker.scalar(text("SELECT pg_backend_pid()"))
        blocker.scalar(
            select(OrganizationRow)
            .where(OrganizationRow.organization_id == data["orgs"][0])
            .with_for_update()
        )

        def worker():
            with session_scope(factory) as session:
                pids.put(session.scalar(text("SELECT pg_backend_pid()")))
                with pytest.raises(CommentBusyError):
                    service(session).create(**args(data))
                assert not session.in_transaction()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(worker)
            try:
                wait_for_database_blocker(
                    factory,
                    worker_pid=pids.get(timeout=5),
                    expected_blocker_pid=blocker_pid,
                )
                with session_scope(factory) as independent:
                    service(independent).create(**args(data, 2))
                future.result(timeout=10)
            finally:
                blocker.rollback()
    assert count(factory) == 1
    assert read(factory, data).page.total_count == 0
