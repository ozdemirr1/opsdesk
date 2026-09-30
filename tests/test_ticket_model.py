from sqlalchemy import BigInteger, DateTime, Text

from opsdesk.db.models.ticket import TicketRow

EXPECTED_COLUMNS = [
    "ticket_id",
    "organization_id",
    "requester_membership_id",
    "creator_membership_id",
    "assignee_membership_id",
    "title",
    "description",
    "status",
    "priority",
    "created_at",
    "updated_at",
]


def test_ticket_table_has_reviewed_columns_and_nullability():
    table = TicketRow.__table__

    assert table.name == "tickets"
    assert list(table.columns.keys()) == EXPECTED_COLUMNS

    assert isinstance(table.c.ticket_id.type, BigInteger)
    assert table.c.ticket_id.identity is not None
    assert table.c.ticket_id.identity.always is True

    assert isinstance(table.c.organization_id.type, BigInteger)
    assert isinstance(
        table.c.requester_membership_id.type,
        BigInteger,
    )
    assert isinstance(
        table.c.creator_membership_id.type,
        BigInteger,
    )
    assert isinstance(
        table.c.assignee_membership_id.type,
        BigInteger,
    )

    assert isinstance(table.c.title.type, Text)
    assert isinstance(table.c.description.type, Text)
    assert isinstance(table.c.status.type, Text)
    assert isinstance(table.c.priority.type, Text)

    assert table.c.assignee_membership_id.nullable is True

    for column_name in EXPECTED_COLUMNS:
        if column_name != "assignee_membership_id":
            assert table.c[column_name].nullable is False


def test_ticket_table_has_reviewed_defaults_and_timestamp_types():
    table = TicketRow.__table__

    assert str(table.c.status.server_default.arg) == "'open'"
    assert str(table.c.priority.server_default.arg) == "'medium'"

    assert isinstance(table.c.created_at.type, DateTime)
    assert table.c.created_at.type.timezone is True
    assert str(table.c.created_at.server_default.arg) == "statement_timestamp()"

    assert isinstance(table.c.updated_at.type, DateTime)
    assert table.c.updated_at.type.timezone is True
    assert str(table.c.updated_at.server_default.arg) == "statement_timestamp()"


def test_ticket_table_has_named_keys_and_check_constraints():
    table = TicketRow.__table__
    constraint_names = {constraint.name for constraint in table.constraints}

    assert {
        "pk_tickets",
        "uq_tickets_org_ticket",
        "ck_tickets_title_length",
        "ck_tickets_description_length",
        "ck_tickets_status",
        "ck_tickets_priority",
        "fk_tickets_organization_id",
        "fk_tickets_requester_membership",
        "fk_tickets_creator_membership",
        "fk_tickets_assignee_membership",
    } <= constraint_names


def test_ticket_foreign_keys_preserve_tenant_consistency():
    table = TicketRow.__table__
    foreign_keys = {
        constraint.name: constraint for constraint in table.foreign_key_constraints
    }

    expected = {
        "fk_tickets_organization_id": (
            ["organization_id"],
            ["organizations.organization_id"],
        ),
        "fk_tickets_requester_membership": (
            [
                "organization_id",
                "requester_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
        ),
        "fk_tickets_creator_membership": (
            [
                "organization_id",
                "creator_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
        ),
        "fk_tickets_assignee_membership": (
            [
                "organization_id",
                "assignee_membership_id",
            ],
            [
                "organization_memberships.organization_id",
                "organization_memberships.membership_id",
            ],
        ),
    }

    assert set(foreign_keys) == set(expected)

    for name, (source_columns, target_columns) in expected.items():
        constraint = foreign_keys[name]

        assert list(constraint.column_keys) == source_columns
        assert [
            element.target_fullname for element in constraint.elements
        ] == target_columns
        assert constraint.ondelete == "RESTRICT"

    assert foreign_keys["fk_tickets_assignee_membership"].match == "SIMPLE"
