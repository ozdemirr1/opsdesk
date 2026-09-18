import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from opsdesk.db.models import OrganizationRow
from opsdesk.db.session import session_scope


def assert_organizations_empty(factory):
    with session_scope(factory) as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM public.organizations")
        ).scalar_one()
        assert count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "name",
    ["Ö", "Ö" * 255, "Özdemir  Yazılım"],
)
def test_accepted_organization_name_and_defaults(identity_scope, name):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            organization = OrganizationRow(name=name)
            session.add(organization)
            session.commit()
            organization_id = organization.organization_id

        with session_scope(factory) as session:
            row = session.execute(
                text(
                    "SELECT organization_id, name, is_active "
                    "FROM public.organizations "
                    "WHERE organization_id = :organization_id"
                ),
                {"organization_id": organization_id},
            ).one()

            assert row.organization_id > 0
            assert row.name == name
            assert row.is_active is True


@pytest.mark.integration
@pytest.mark.parametrize("name", ["", "Ö" * 256])
def test_invalid_organization_name_length_is_rejected(identity_scope, name):
    with identity_scope() as factory:
        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(factory) as session:
                session.add(OrganizationRow(name=name))
                session.commit()

        assert exc_info.value.orig.sqlstate == "23514"
        assert (
            exc_info.value.orig.diag.constraint_name == "ck_organizations_name_length"
        )
        assert_organizations_empty(factory)


@pytest.mark.integration
@pytest.mark.parametrize("column_name", ["name", "is_active"])
def test_required_organization_fields_reject_null(identity_scope, column_name):
    values = {
        "name": "Required Fields Organization",
        "is_active": True,
    }
    values[column_name] = None

    with identity_scope() as factory:
        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(factory) as session:
                session.execute(
                    text(
                        "INSERT INTO public.organizations (name, is_active) "
                        "VALUES (:name, :is_active)"
                    ),
                    values,
                )
                session.commit()

        assert exc_info.value.orig.sqlstate == "23502"
        assert exc_info.value.orig.diag.table_name == "organizations"
        assert exc_info.value.orig.diag.column_name == column_name
        assert_organizations_empty(factory)


@pytest.mark.integration
def test_organizations_can_share_the_same_name(identity_scope):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            first = OrganizationRow(name="Shared Name")
            second = OrganizationRow(name="Shared Name")
            session.add_all([first, second])
            session.commit()
            expected_ids = {first.organization_id, second.organization_id}

        with session_scope(factory) as session:
            rows = session.execute(
                text(
                    "SELECT organization_id, name, is_active FROM public.organizations"
                )
            ).all()

            assert len(rows) == 2
            assert len(expected_ids) == 2
            assert {row.organization_id for row in rows} == expected_ids
            assert all(row.name == "Shared Name" for row in rows)
            assert all(row.is_active is True for row in rows)
