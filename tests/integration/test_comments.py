from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, func, inspect, select, update
from sqlalchemy.exc import IntegrityError

from opsdesk.comments.models import NewComment
from opsdesk.db.models import (
    CommentRow,
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.repositories.comments import SqlAlchemyCommentRepository
from opsdesk.db.session import session_scope

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


@pytest.fixture
def context(identity_scope):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            users = [
                UserRow(
                    email=f"comment-{i}@example.com", password_hash="synthetic-hash"
                )
                for i in range(3)
            ]
            orgs = [OrganizationRow(name=f"Comment organization {i}") for i in range(2)]
            session.add_all(users + orgs)
            session.flush()
            memberships = [
                OrganizationMembershipRow(
                    user_id=users[i].user_id,
                    organization_id=orgs[0 if i < 2 else 1].organization_id,
                    role="customer",
                )
                for i in range(3)
            ]
            session.add_all(memberships)
            session.flush()
            tickets = [
                TicketRow(
                    organization_id=m.organization_id,
                    requester_membership_id=m.membership_id,
                    creator_membership_id=m.membership_id,
                    title="Synthetic issue",
                    description="Synthetic details",
                )
                for m in memberships
            ]
            session.add_all(tickets)
            session.commit()
            data = {
                "users": [u.user_id for u in users],
                "orgs": [o.organization_id for o in orgs],
                "members": [m.membership_id for m in memberships],
                "tickets": [t.ticket_id for t in tickets],
            }
        yield factory, data


def values(data, i=0, **overrides):
    result = dict(
        organization_id=data["orgs"][0 if i < 2 else 1],
        ticket_id=data["tickets"][i],
        author_membership_id=data["members"][i],
        content="Comment text",
    )
    result.update(overrides)
    return result


def insert(factory, data, i=0, **overrides):
    with session_scope(factory) as session:
        row = CommentRow(**values(data, i, **overrides))
        session.add(row)
        session.commit()
        return row.comment_id


def read(factory, data, i=0, **overrides):
    args = dict(
        actor_user_id=data["users"][0],
        organization_id=data["orgs"][0],
        ticket_id=data["tickets"][i],
        limit=20,
        offset=0,
    )
    args.update(overrides)
    with session_scope(factory) as session:
        return SqlAlchemyCommentRepository(session).list_for_actor(**args)


def test_migrated_schema_matches_comment_contract(integration_engine):
    with integration_engine.connect() as connection:
        inspector = inspect(connection)
        cols = {c["name"]: c for c in inspector.get_columns("comments")}
        assert list(cols) == [
            "comment_id",
            "organization_id",
            "ticket_id",
            "author_membership_id",
            "content",
            "created_at",
        ]
        assert all(not c["nullable"] for c in cols.values())
        assert cols["comment_id"]["identity"]["always"]
        assert cols["created_at"]["type"].timezone
        assert "statement_timestamp()" in cols["created_at"]["default"]
        fks = {fk["name"]: fk for fk in inspector.get_foreign_keys("comments")}
        assert fks["fk_comments_ticket"]["constrained_columns"] == [
            "organization_id",
            "ticket_id",
        ]
        assert fks["fk_comments_author_membership"]["constrained_columns"] == [
            "organization_id",
            "author_membership_id",
        ]
        assert all(fk["options"]["ondelete"] == "RESTRICT" for fk in fks.values())
        indexes = {index["name"]: index for index in inspector.get_indexes("comments")}
        assert indexes["ix_comments_ticket_chronology"]["column_names"] == [
            "organization_id",
            "ticket_id",
            "created_at",
            "comment_id",
        ]


def test_create_flushes_without_committing_and_does_not_change_ticket(context):
    factory, data = context
    with session_scope(factory) as session:
        before = session.get(TicketRow, data["tickets"][0]).updated_at
        comment = SqlAlchemyCommentRepository(session).create(
            NewComment(
                **values(data, content="First line.\nSecond line: erişim hatası.")
            )
        )
        assert comment.created_at.utcoffset() is not None
        assert comment.content == "First line.\nSecond line: erişim hatası."
        with session_scope(factory) as observer:
            assert observer.scalar(select(func.count()).select_from(CommentRow)) == 0
        session.rollback()
        assert session.scalar(select(func.count()).select_from(CommentRow)) == 0
        committed = SqlAlchemyCommentRepository(session).create(
            NewComment(**values(data))
        )
        session.commit()
        assert committed.comment_id != comment.comment_id
        session.expire_all()
        ticket = session.get(TicketRow, data["tickets"][0])
        assert ticket.updated_at == before and ticket.status == "open"
    assert read(factory, data).page.items[0].comment_id == committed.comment_id


@pytest.mark.parametrize("content", ["x", "🙂" * 10000])
def test_database_content_boundaries(context, content):
    factory, data = context
    insert(factory, data, content=content)
    assert read(factory, data).page.items[0].content == content


@pytest.mark.parametrize("content", ["", "x" * 10001])
def test_database_rejects_invalid_lengths(context, content):
    factory, data = context
    with pytest.raises(IntegrityError) as error:
        insert(factory, data, content=content)
    assert error.value.orig.diag.constraint_name == "ck_comments_content_length"
    assert read(factory, data).page.total_count == 0


@pytest.mark.parametrize(
    "field",
    ["organization_id", "ticket_id", "author_membership_id", "content", "created_at"],
)
def test_required_fields_reject_explicit_null(context, field):
    factory, data = context
    with session_scope(factory) as session:
        with pytest.raises(IntegrityError) as error:
            session.execute(
                CommentRow.__table__.insert().values(**values(data, **{field: None}))
            )
        assert error.value.orig.sqlstate == "23502"
        session.rollback()


@pytest.mark.parametrize(
    "field,constraint",
    [
        ("ticket_id", "fk_comments_ticket"),
        ("author_membership_id", "fk_comments_author_membership"),
    ],
)
@pytest.mark.parametrize("missing", [False, True])
def test_wrong_tenant_and_missing_references_are_rejected(
    context, field, constraint, missing
):
    factory, data = context
    value = (
        999999999
        if missing
        else data["tickets" if field == "ticket_id" else "members"][2]
    )
    with pytest.raises(IntegrityError) as error:
        insert(factory, data, **{field: value})
    assert error.value.orig.sqlstate == "23503"
    assert error.value.orig.diag.constraint_name == constraint


def test_referenced_ticket_cannot_be_deleted(context):
    factory, data = context
    insert(factory, data)
    with session_scope(factory) as session:
        with pytest.raises(IntegrityError) as error:
            session.execute(
                TicketRow.__table__.delete().where(
                    TicketRow.ticket_id == data["tickets"][0]
                )
            )
        assert error.value.orig.diag.constraint_name == "fk_comments_ticket"
        session.rollback()


def test_author_attribution_survives_deactivation_and_blocks_deletion(context):
    factory, data = context
    # The author is not the parent Ticket's requester/creator, avoiding a false-positive FK test.
    insert(factory, data, author_membership_id=data["members"][1])
    with session_scope(factory) as session:
        session.execute(
            TicketRow.__table__.delete().where(
                TicketRow.ticket_id == data["tickets"][1]
            )
        )
        session.execute(
            update(OrganizationMembershipRow)
            .where(OrganizationMembershipRow.membership_id == data["members"][1])
            .values(is_active=False)
        )
        session.commit()
        with pytest.raises(IntegrityError) as error:
            session.execute(
                OrganizationMembershipRow.__table__.delete().where(
                    OrganizationMembershipRow.membership_id == data["members"][1]
                )
            )
        assert error.value.orig.diag.constraint_name == "fk_comments_author_membership"
        session.rollback()
    assert read(factory, data).page.items[0].author_membership_id == data["members"][1]


@pytest.mark.parametrize(
    "role,visible",
    [("customer", False), ("agent", True), ("admin", True), ("owner", True)],
)
def test_parent_visibility_scopes_items_and_count(context, role, visible):
    factory, data = context
    for i in range(3):
        insert(factory, data, i)
    with session_scope(factory) as session:
        session.execute(
            update(OrganizationMembershipRow)
            .where(OrganizationMembershipRow.membership_id == data["members"][0])
            .values(role=role)
        )
        session.commit()
    own = read(factory, data)
    other = read(factory, data, 1)
    foreign = read(factory, data, 2)
    assert own.ticket_visible and own.page.total_count == 1
    assert other.ticket_visible is visible
    assert other.page.total_count == int(visible)
    assert (
        not foreign.ticket_visible
        and foreign.page.items == ()
        and foreign.page.total_count == 0
    )


@pytest.mark.parametrize("inactive", ["user", "membership", "organization"])
def test_inactive_context_hides_comments_and_counts(context, inactive):
    factory, data = context
    insert(factory, data)
    model, key, value = {
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
        session.execute(update(model).where(key == value).values(is_active=False))
        session.commit()
    result = read(factory, data)
    assert (
        not result.ticket_visible
        and result.page.total_count == 0
        and result.page.items == ()
    )
    assert not getattr(
        result.access, "actor_active" if inactive == "user" else inactive + "_active"
    )


def test_missing_parent_and_empty_parent_are_distinct(context):
    factory, data = context
    empty = read(factory, data)
    missing = read(factory, data, ticket_id=999999999)
    assert empty.ticket_visible and not missing.ticket_visible
    assert empty.page.items == missing.page.items == ()


def test_reads_closed_tickets_and_stable_chronological_pages_in_one_statement(context):
    factory, data = context
    late = insert(factory, data, created_at=NOW + timedelta(seconds=1))
    first = insert(factory, data, created_at=NOW)
    second = insert(factory, data, created_at=NOW)
    with session_scope(factory) as session:
        session.execute(
            update(TicketRow)
            .where(TicketRow.ticket_id == data["tickets"][0])
            .values(status="closed")
        )
        session.commit()
        calls = []
        connection = session.connection()

        def capture(conn, cursor, statement, parameters, context, executemany):
            calls.append(statement)

        event.listen(connection, "before_cursor_execute", capture)
        try:
            result = SqlAlchemyCommentRepository(session).list_for_actor(
                actor_user_id=data["users"][0],
                organization_id=data["orgs"][0],
                ticket_id=data["tickets"][0],
                limit=2,
                offset=0,
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture)
        assert len(calls) == 1
    assert result.ticket_visible and result.page.total_count == 3
    assert [c.comment_id for c in result.page.items] == [first, second]
    assert [
        c.comment_id for c in read(factory, data, limit=2, offset=2).page.items
    ] == [late]
    beyond = read(factory, data, limit=2, offset=100)
    assert (
        beyond.page.total_count == 3
        and beyond.page.items == ()
        and beyond.ticket_visible
    )
