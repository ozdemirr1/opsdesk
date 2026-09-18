import pytest
from sqlalchemy import BigInteger, inspect, text


@pytest.mark.integration
def test_initial_identity_schema_exists(integration_engine):
    expected_columns = {
        "users": {"user_id", "email", "password_hash", "is_active"},
        "organizations": {"organization_id", "name", "is_active"},
        "organization_memberships": {
            "membership_id",
            "user_id",
            "organization_id",
            "role",
            "is_active",
        },
    }

    with integration_engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        assert revision == "6a3066cd5538"

        inspector = inspect(connection)
        actual_tables = set(inspector.get_table_names(schema="public"))
        assert set(expected_columns).issubset(actual_tables)

        for table_name, column_names in expected_columns.items():
            columns = inspector.get_columns(table_name, schema="public")
            assert {column["name"] for column in columns} == column_names
            assert all(column["nullable"] is False for column in columns)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("table_name", "id_column", "primary_key_name"),
    [
        ("users", "user_id", "pk_users"),
        ("organizations", "organization_id", "pk_organizations"),
        (
            "organization_memberships",
            "membership_id",
            "pk_organization_memberships",
        ),
    ],
)
def test_primary_keys_use_bigint_generated_always_identity(
    integration_engine, table_name, id_column, primary_key_name
):
    with integration_engine.connect() as connection:
        inspector = inspect(connection)
        columns = {
            column["name"]: column
            for column in inspector.get_columns(table_name, schema="public")
        }

        column = columns[id_column]
        assert isinstance(column["type"], BigInteger)
        assert column["identity"]["always"] is True

        primary_key = inspector.get_pk_constraint(table_name, schema="public")
        assert primary_key["name"] == primary_key_name
        assert primary_key["constrained_columns"] == [id_column]


@pytest.mark.integration
def test_membership_composite_unique_constraints_exist(integration_engine):
    with integration_engine.connect() as connection:
        inspector = inspect(connection)
        constraints = {
            constraint["name"]: constraint["column_names"]
            for constraint in inspector.get_unique_constraints(
                "organization_memberships",
                schema="public",
            )
        }

        assert constraints["uq_memberships_user_org"] == [
            "user_id",
            "organization_id",
        ]
        assert constraints["uq_memberships_org_membership"] == [
            "organization_id",
            "membership_id",
        ]
