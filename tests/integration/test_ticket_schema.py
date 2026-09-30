import pytest
from sqlalchemy import BigInteger, DateTime, Text, inspect, text

HEAD_REVISION = "31be9023cfb2"

pytestmark = pytest.mark.integration


def test_ticket_schema_has_reviewed_columns_and_defaults(
    integration_engine,
):
    with integration_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        assert revision == HEAD_REVISION

        columns = {
            column["name"]: column
            for column in inspect(connection).get_columns(
                "tickets",
                schema="public",
            )
        }

    assert list(columns) == [
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

    bigint_columns = {
        "ticket_id",
        "organization_id",
        "requester_membership_id",
        "creator_membership_id",
        "assignee_membership_id",
    }
    for column_name in bigint_columns:
        assert isinstance(
            columns[column_name]["type"],
            BigInteger,
        )

    for column_name in {
        "title",
        "description",
        "status",
        "priority",
    }:
        assert isinstance(columns[column_name]["type"], Text)

    for column_name in {"created_at", "updated_at"}:
        column_type = columns[column_name]["type"]
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True
        assert "statement_timestamp()" in columns[column_name]["default"]

    assert columns["ticket_id"]["identity"]["always"] is True
    assert columns["assignee_membership_id"]["nullable"] is True

    for column_name, column in columns.items():
        if column_name != "assignee_membership_id":
            assert column["nullable"] is False

    assert "'open'" in columns["status"]["default"]
    assert "'medium'" in columns["priority"]["default"]


def test_ticket_schema_has_reviewed_named_constraints(
    integration_engine,
):
    with integration_engine.connect() as connection:
        inspector = inspect(connection)

        primary_key = inspector.get_pk_constraint(
            "tickets",
            schema="public",
        )
        unique_constraints = {
            constraint["name"]: constraint["column_names"]
            for constraint in inspector.get_unique_constraints(
                "tickets",
                schema="public",
            )
        }
        check_constraints = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(
                "tickets",
                schema="public",
            )
        }

    assert primary_key["name"] == "pk_tickets"
    assert primary_key["constrained_columns"] == ["ticket_id"]

    assert unique_constraints["uq_tickets_org_ticket"] == [
        "organization_id",
        "ticket_id",
    ]

    assert {
        "ck_tickets_title_length",
        "ck_tickets_description_length",
        "ck_tickets_status",
        "ck_tickets_priority",
    } <= check_constraints


def test_ticket_schema_has_tenant_consistent_foreign_keys(
    integration_engine,
):
    expected = {
        "fk_tickets_organization_id": (
            ["organization_id"],
            "organizations",
            ["organization_id"],
        ),
        "fk_tickets_requester_membership": (
            [
                "organization_id",
                "requester_membership_id",
            ],
            "organization_memberships",
            [
                "organization_id",
                "membership_id",
            ],
        ),
        "fk_tickets_creator_membership": (
            [
                "organization_id",
                "creator_membership_id",
            ],
            "organization_memberships",
            [
                "organization_id",
                "membership_id",
            ],
        ),
        "fk_tickets_assignee_membership": (
            [
                "organization_id",
                "assignee_membership_id",
            ],
            "organization_memberships",
            [
                "organization_id",
                "membership_id",
            ],
        ),
    }

    with integration_engine.connect() as connection:
        foreign_keys = {
            foreign_key["name"]: foreign_key
            for foreign_key in inspect(connection).get_foreign_keys(
                "tickets",
                schema="public",
            )
        }

        catalog_rows = connection.execute(
            text(
                "SELECT conname, confmatchtype, confdeltype "
                "FROM pg_catalog.pg_constraint "
                "WHERE conrelid = 'public.tickets'::regclass "
                "AND contype = 'f'"
            )
        ).all()

    assert set(foreign_keys) == set(expected)

    for name, (
        source_columns,
        referred_table,
        referred_columns,
    ) in expected.items():
        foreign_key = foreign_keys[name]

        assert foreign_key["constrained_columns"] == source_columns
        assert foreign_key["referred_schema"] in {
            None,
            "public",
        }
        assert foreign_key["referred_table"] == referred_table
        assert foreign_key["referred_columns"] == referred_columns
        assert foreign_key["options"].get("ondelete") == "RESTRICT"

    catalog = {
        row.conname: (
            row.confmatchtype,
            row.confdeltype,
        )
        for row in catalog_rows
    }

    assert set(catalog) == set(expected)

    for match_type, delete_action in catalog.values():
        assert match_type == "s"
        assert delete_action == "r"
