from contextlib import nullcontext

import pytest
from sqlalchemy import text

from opsdesk.db.models import OrganizationMembershipRow, OrganizationRow, UserRow
from opsdesk.db.session import session_scope


def read_identity_counts(connection):
    return tuple(
        connection.execute(
            text(
                "SELECT "
                "(SELECT COUNT(*) FROM public.users), "
                "(SELECT COUNT(*) FROM public.organizations), "
                "(SELECT COUNT(*) FROM public.organization_memberships)"
            )
        ).one()
    )


@pytest.mark.integration
@pytest.mark.parametrize("body_fails", [False, True])
def test_committed_identity_records_are_visible_and_cleaned(
    identity_scope, integration_engine, body_fails
):
    expectation = (
        pytest.raises(RuntimeError, match=r"^Synthetic identity body failure\.$")
        if body_fails
        else nullcontext()
    )

    with expectation, identity_scope() as factory:
        with session_scope(factory) as session:
            user = UserRow(
                email="identity-cleanup@example.com",
                password_hash="test-only-hash-placeholder",
            )
            organization = OrganizationRow(name="Cleanup Test Organization")
            session.add_all([user, organization])
            session.flush()

            membership = OrganizationMembershipRow(
                user_id=user.user_id,
                organization_id=organization.organization_id,
                role="owner",
            )
            session.add(membership)
            session.commit()

        with integration_engine.connect() as connection:
            assert read_identity_counts(connection) == (1, 1, 1)

        if body_fails:
            raise RuntimeError("Synthetic identity body failure.")

    with integration_engine.connect() as connection:
        assert read_identity_counts(connection) == (0, 0, 0)

        revision = connection.execute(
            text("SELECT version_num FROM public.alembic_version")
        ).scalar_one()
        assert revision == "6a3066cd5538"
