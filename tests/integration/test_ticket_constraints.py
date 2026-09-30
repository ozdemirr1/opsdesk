from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from opsdesk.db.models import (
    OrganizationMembershipRow,
    OrganizationRow,
    TicketRow,
    UserRow,
)
from opsdesk.db.session import session_scope

pytestmark = pytest.mark.integration

MEMBERSHIPS = OrganizationMembershipRow.__table__
TICKETS = TicketRow.__table__


def seed_ticket_context(factory) -> dict[str, int]:
    with session_scope(factory) as session:
        users = [
            UserRow(
                email=f"ticket-member-{number}@example.com",
                password_hash="test-only-hash-placeholder",
            )
            for number in range(5)
        ]
        organizations = [
            OrganizationRow(name="Ticket Organization"),
            OrganizationRow(name="Foreign Organization"),
        ]
        session.add_all([*users, *organizations])
        session.flush()

        memberships = [
            OrganizationMembershipRow(
                user_id=users[0].user_id,
                organization_id=organizations[0].organization_id,
                role="customer",
            ),
            OrganizationMembershipRow(
                user_id=users[1].user_id,
                organization_id=organizations[0].organization_id,
                role="agent",
            ),
            OrganizationMembershipRow(
                user_id=users[2].user_id,
                organization_id=organizations[0].organization_id,
                role="admin",
            ),
            OrganizationMembershipRow(
                user_id=users[3].user_id,
                organization_id=organizations[0].organization_id,
                role="customer",
                is_active=False,
            ),
            OrganizationMembershipRow(
                user_id=users[4].user_id,
                organization_id=organizations[1].organization_id,
                role="agent",
            ),
        ]
        session.add_all(memberships)
        session.commit()

        return {
            "organization_id": organizations[0].organization_id,
            "foreign_organization_id": (organizations[1].organization_id),
            "requester_membership_id": (memberships[0].membership_id),
            "creator_membership_id": (memberships[1].membership_id),
            "assignee_membership_id": (memberships[2].membership_id),
            "inactive_customer_membership_id": (memberships[3].membership_id),
            "foreign_membership_id": (memberships[4].membership_id),
        }


def ticket_insert(context, **overrides):
    values = {
        "organization_id": context["organization_id"],
        "requester_membership_id": (context["requester_membership_id"]),
        "creator_membership_id": (context["creator_membership_id"]),
        "title": "Ticket title",
        "description": "Ticket description",
    }
    values.update(overrides)

    return TICKETS.insert().values(**values).returning(TICKETS.c.ticket_id)


def persist(factory, statement):
    with session_scope(factory) as session:
        result = session.execute(statement)
        returned_id = result.scalar_one() if result.returns_rows else None
        session.commit()
        return returned_id


def read_business_state(factory):
    with session_scope(factory) as session:
        membership_rows = session.execute(
            select(MEMBERSHIPS).order_by(MEMBERSHIPS.c.membership_id)
        ).all()
        ticket_rows = session.execute(
            select(TICKETS).order_by(TICKETS.c.ticket_id)
        ).all()

        return (
            [tuple(row) for row in membership_rows],
            [tuple(row) for row in ticket_rows],
        )


def read_ticket(factory, ticket_id):
    with session_scope(factory) as session:
        return (
            session.execute(select(TICKETS).where(TICKETS.c.ticket_id == ticket_id))
            .mappings()
            .one()
        )


def assert_rejected(
    factory,
    statement,
    sqlstate,
    *,
    constraint=None,
    column=None,
):
    before = read_business_state(factory)

    with pytest.raises(IntegrityError) as exc_info:
        persist(factory, statement)

    error = exc_info.value.orig

    assert error.sqlstate == sqlstate
    assert error.diag.table_name == "tickets"

    if constraint is not None:
        assert error.diag.constraint_name == constraint

    if column is not None:
        assert error.diag.column_name == column

    assert read_business_state(factory) == before


def test_valid_ticket_uses_database_defaults_and_null_assignee(
    identity_scope,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        ticket_id = persist(
            factory,
            ticket_insert(context),
        )

        row = read_ticket(factory, ticket_id)

        assert row["ticket_id"] == ticket_id
        assert row["organization_id"] == (context["organization_id"])
        assert row["requester_membership_id"] == (context["requester_membership_id"])
        assert row["creator_membership_id"] == (context["creator_membership_id"])
        assert row["assignee_membership_id"] is None
        assert row["status"] == "open"
        assert row["priority"] == "medium"
        assert isinstance(row["created_at"], datetime)
        assert row["created_at"].utcoffset() is not None
        assert row["created_at"] == row["updated_at"]


@pytest.mark.parametrize(
    "status",
    [
        "open",
        "in_progress",
        "resolved",
        "closed",
    ],
)
def test_valid_ticket_status_values_are_stored(
    identity_scope,
    status,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        ticket_id = persist(
            factory,
            ticket_insert(
                context,
                status=status,
            ),
        )

        assert read_ticket(factory, ticket_id)["status"] == status


@pytest.mark.parametrize(
    "priority",
    [
        "low",
        "medium",
        "high",
        "urgent",
    ],
)
def test_valid_ticket_priority_values_are_stored(
    identity_scope,
    priority,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        ticket_id = persist(
            factory,
            ticket_insert(
                context,
                priority=priority,
            ),
        )

        assert read_ticket(factory, ticket_id)["priority"] == priority


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("title", "A"),
        ("title", "A" * 255),
        ("description", "B"),
        ("description", "B" * 10_000),
    ],
)
def test_ticket_text_boundaries_are_accepted(
    identity_scope,
    field_name,
    value,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        ticket_id = persist(
            factory,
            ticket_insert(
                context,
                **{field_name: value},
            ),
        )

        assert read_ticket(factory, ticket_id)[field_name] == value


@pytest.mark.parametrize(
    ("field_name", "value", "constraint"),
    [
        (
            "title",
            "",
            "ck_tickets_title_length",
        ),
        (
            "title",
            "A" * 256,
            "ck_tickets_title_length",
        ),
        (
            "description",
            "",
            "ck_tickets_description_length",
        ),
        (
            "description",
            "B" * 10_001,
            "ck_tickets_description_length",
        ),
    ],
)
def test_invalid_ticket_text_lengths_are_rejected(
    identity_scope,
    field_name,
    value,
    constraint,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        assert_rejected(
            factory,
            ticket_insert(
                context,
                **{field_name: value},
            ),
            "23514",
            constraint=constraint,
        )


@pytest.mark.parametrize(
    ("field_name", "value", "constraint"),
    [
        (
            "status",
            "",
            "ck_tickets_status",
        ),
        (
            "status",
            "Open",
            "ck_tickets_status",
        ),
        (
            "status",
            " open ",
            "ck_tickets_status",
        ),
        (
            "status",
            "waiting",
            "ck_tickets_status",
        ),
        (
            "priority",
            "",
            "ck_tickets_priority",
        ),
        (
            "priority",
            "High",
            "ck_tickets_priority",
        ),
        (
            "priority",
            " high ",
            "ck_tickets_priority",
        ),
        (
            "priority",
            "critical",
            "ck_tickets_priority",
        ),
    ],
)
def test_invalid_ticket_vocabulary_is_rejected(
    identity_scope,
    field_name,
    value,
    constraint,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        assert_rejected(
            factory,
            ticket_insert(
                context,
                **{field_name: value},
            ),
            "23514",
            constraint=constraint,
        )


@pytest.mark.parametrize(
    "column_name",
    [
        "organization_id",
        "requester_membership_id",
        "creator_membership_id",
        "title",
        "description",
        "status",
        "priority",
        "created_at",
        "updated_at",
    ],
)
def test_required_ticket_fields_reject_explicit_null(
    identity_scope,
    column_name,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        assert_rejected(
            factory,
            ticket_insert(
                context,
                **{column_name: None},
            ),
            "23502",
            column=column_name,
        )


@pytest.mark.parametrize(
    ("participant_field", "constraint"),
    [
        (
            "requester_membership_id",
            "fk_tickets_requester_membership",
        ),
        (
            "creator_membership_id",
            "fk_tickets_creator_membership",
        ),
        (
            "assignee_membership_id",
            "fk_tickets_assignee_membership",
        ),
    ],
)
def test_cross_tenant_participants_are_rejected(
    identity_scope,
    participant_field,
    constraint,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        assert_rejected(
            factory,
            ticket_insert(
                context,
                **{participant_field: (context["foreign_membership_id"])},
            ),
            "23503",
            constraint=constraint,
        )


@pytest.mark.parametrize(
    ("participant_field", "constraint"),
    [
        (
            "requester_membership_id",
            "fk_tickets_requester_membership",
        ),
        (
            "creator_membership_id",
            "fk_tickets_creator_membership",
        ),
        (
            "assignee_membership_id",
            "fk_tickets_assignee_membership",
        ),
    ],
)
def test_missing_participant_memberships_are_rejected(
    identity_scope,
    participant_field,
    constraint,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        missing_membership_id = max(context.values()) + 10_000

        assert_rejected(
            factory,
            ticket_insert(
                context,
                **{participant_field: (missing_membership_id)},
            ),
            "23503",
            constraint=constraint,
        )


def test_database_constraints_do_not_replace_assignment_rules(
    identity_scope,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        ticket_id = persist(
            factory,
            ticket_insert(
                context,
                assignee_membership_id=context["inactive_customer_membership_id"],
                status="in_progress",
            ),
        )

        row = read_ticket(factory, ticket_id)

        assert (
            row["assignee_membership_id"] == context["inactive_customer_membership_id"]
        )
        assert row["status"] == "in_progress"


def test_updated_at_does_not_refresh_automatically(
    identity_scope,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)
        ticket_id = persist(
            factory,
            ticket_insert(context),
        )
        original = read_ticket(factory, ticket_id)

        persist(
            factory,
            TICKETS.update()
            .where(TICKETS.c.ticket_id == ticket_id)
            .values(priority="high"),
        )

        updated = read_ticket(factory, ticket_id)

        assert updated["priority"] == "high"
        assert updated["created_at"] == original["created_at"]
        assert updated["updated_at"] == original["updated_at"]


def test_repeated_ticket_titles_are_allowed(
    identity_scope,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        first_id = persist(
            factory,
            ticket_insert(
                context,
                title="Repeated title",
            ),
        )
        second_id = persist(
            factory,
            ticket_insert(
                context,
                title="Repeated title",
            ),
        )

        assert first_id != second_id
        assert len(read_business_state(factory)[1]) == 2


@pytest.mark.parametrize(
    ("participant", "constraint"),
    [
        (
            "requester_membership_id",
            "fk_tickets_requester_membership",
        ),
        (
            "creator_membership_id",
            "fk_tickets_creator_membership",
        ),
        (
            "assignee_membership_id",
            "fk_tickets_assignee_membership",
        ),
    ],
)
def test_referenced_membership_cannot_be_deleted(
    identity_scope,
    participant,
    constraint,
):
    with identity_scope() as factory:
        context = seed_ticket_context(factory)

        persist(
            factory,
            ticket_insert(
                context,
                assignee_membership_id=context["assignee_membership_id"],
            ),
        )

        membership_id = context[participant]
        statement = MEMBERSHIPS.delete().where(
            MEMBERSHIPS.c.membership_id == membership_id
        )

        assert_rejected(
            factory,
            statement,
            "23001",
            constraint=constraint,
        )
