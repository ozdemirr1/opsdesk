import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from opsdesk.db.models import OrganizationMembershipRow, OrganizationRow, UserRow
from opsdesk.db.session import session_scope

pytestmark = pytest.mark.integration

USERS = UserRow.__table__
ORGANIZATIONS = OrganizationRow.__table__
MEMBERSHIPS = OrganizationMembershipRow.__table__


def seed_parents(factory, organization_active=True):
    with session_scope(factory) as session:
        users = [
            UserRow(
                email=f"member{number}@example.com",
                password_hash="test-only-hash-placeholder",
            )
            for number in range(2)
        ]
        organizations = [
            OrganizationRow(
                name=f"Organization {number}",
                is_active=organization_active,
            )
            for number in range(2)
        ]
        session.add_all([*users, *organizations])
        session.commit()

        return (
            [user.user_id for user in users],
            [organization.organization_id for organization in organizations],
        )


def persist(factory, statement):
    with session_scope(factory) as session:
        result = session.execute(statement)
        returned_id = result.scalar_one() if result.returns_rows else None
        session.commit()
        return returned_id


def membership_insert(user_id, organization_id, **overrides):
    values = {
        "user_id": user_id,
        "organization_id": organization_id,
        "role": "customer",
    }
    values.update(overrides)
    return MEMBERSHIPS.insert().values(**values).returning(MEMBERSHIPS.c.membership_id)


def read_identity_state(factory):
    state = []
    with session_scope(factory) as session:
        for table in (USERS, ORGANIZATIONS, MEMBERSHIPS):
            primary_key = list(table.primary_key.columns)[0]
            rows = session.execute(select(table).order_by(primary_key)).all()
            state.append([tuple(row) for row in rows])
    return state


def assert_rejected(factory, statement, sqlstate, *, constraint=None, column=None):
    before = read_identity_state(factory)

    with pytest.raises(IntegrityError) as exc_info:
        persist(factory, statement)

    error = exc_info.value.orig
    assert error.sqlstate == sqlstate
    assert error.diag.table_name == "organization_memberships"

    if constraint is not None:
        assert error.diag.constraint_name == constraint
    if column is not None:
        assert error.diag.column_name == column

    assert read_identity_state(factory) == before


@pytest.mark.parametrize("role", ["owner", "admin", "agent", "customer"])
def test_valid_roles_and_default_active_state(identity_scope, role):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        membership_id = persist(
            factory,
            membership_insert(users[0], organizations[0], role=role),
        )

        assert membership_id > 0
        assert read_identity_state(factory)[2] == [
            (membership_id, users[0], organizations[0], role, True)
        ]


@pytest.mark.parametrize("role", ["manager", "Owner", " admin ", ""])
def test_invalid_roles_are_rejected(identity_scope, role):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        assert_rejected(
            factory,
            membership_insert(users[0], organizations[0], role=role),
            "23514",
            constraint="ck_memberships_role",
        )


@pytest.mark.parametrize(
    "column_name", ["user_id", "organization_id", "role", "is_active"]
)
def test_required_membership_fields_reject_null(identity_scope, column_name):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        values = {
            "user_id": users[0],
            "organization_id": organizations[0],
            "role": "customer",
            "is_active": True,
        }
        values[column_name] = None

        assert_rejected(
            factory,
            MEMBERSHIPS.insert().values(**values),
            "23502",
            column=column_name,
        )


def test_role_has_no_default(identity_scope):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        assert_rejected(
            factory,
            MEMBERSHIPS.insert().values(
                user_id=users[0],
                organization_id=organizations[0],
            ),
            "23502",
            column="role",
        )


@pytest.mark.parametrize(
    ("missing_parent", "constraint"),
    [
        ("user", "fk_memberships_user_id"),
        ("organization", "fk_memberships_organization_id"),
    ],
)
def test_missing_parent_is_rejected(identity_scope, missing_parent, constraint):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        user_id = max(users) + 1 if missing_parent == "user" else users[0]
        organization_id = (
            max(organizations) + 1
            if missing_parent == "organization"
            else organizations[0]
        )

        assert_rejected(
            factory,
            membership_insert(user_id, organization_id),
            "23503",
            constraint=constraint,
        )


@pytest.mark.parametrize("existing_is_active", [True, False])
def test_duplicate_membership_pair_is_rejected(identity_scope, existing_is_active):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        persist(
            factory,
            membership_insert(users[0], organizations[0], is_active=existing_is_active),
        )

        assert_rejected(
            factory,
            membership_insert(users[0], organizations[0], role="agent"),
            "23505",
            constraint="uq_memberships_user_org",
        )


def test_distinct_user_organization_pairs_are_allowed(identity_scope):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        expected = [
            (users[0], organizations[0], "owner"),
            (users[0], organizations[1], "owner"),
            (users[1], organizations[0], "customer"),
        ]

        for user_id, organization_id, role in expected:
            persist(
                factory,
                membership_insert(user_id, organization_id, role=role),
            )

        rows = read_identity_state(factory)[2]
        assert len(rows) == 3
        assert {(row[1], row[2], row[3]) for row in rows} == set(expected)
        assert all(row[4] is True for row in rows)


@pytest.mark.parametrize(
    ("parent", "constraint"),
    [
        ("user", "fk_memberships_user_id"),
        ("organization", "fk_memberships_organization_id"),
    ],
)
def test_referenced_parent_cannot_be_deleted(identity_scope, parent, constraint):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        persist(factory, membership_insert(users[0], organizations[0]))

        if parent == "user":
            statement = USERS.delete().where(USERS.c.user_id == users[0])
        else:
            statement = ORGANIZATIONS.delete().where(
                ORGANIZATIONS.c.organization_id == organizations[0]
            )

        assert_rejected(
            factory,
            statement,
            "23001",
            constraint=constraint,
        )


@pytest.mark.parametrize("organization_active", [True, False])
def test_second_active_owner_is_rejected(identity_scope, organization_active):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory, organization_active)
        persist(
            factory,
            membership_insert(users[0], organizations[0], role="owner"),
        )

        assert_rejected(
            factory,
            membership_insert(users[1], organizations[0], role="owner"),
            "23505",
            constraint="uq_memberships_active_owner_per_org",
        )


def test_inactive_owners_and_reactivation_boundary(identity_scope):
    with identity_scope() as factory:
        users, organizations = seed_parents(factory)
        membership_ids = [
            persist(
                factory,
                membership_insert(
                    user_id,
                    organizations[0],
                    role="owner",
                    is_active=False,
                ),
            )
            for user_id in users
        ]

        rows = read_identity_state(factory)[2]
        assert len(rows) == 2
        assert all(row[3] == "owner" and row[4] is False for row in rows)

        persist(
            factory,
            MEMBERSHIPS.update()
            .where(MEMBERSHIPS.c.membership_id == membership_ids[0])
            .values(is_active=True),
        )
        rows = read_identity_state(factory)[2]
        assert sum(row[3] == "owner" and row[4] is True for row in rows) == 1

        assert_rejected(
            factory,
            MEMBERSHIPS.update()
            .where(MEMBERSHIPS.c.membership_id == membership_ids[1])
            .values(is_active=True),
            "23505",
            constraint="uq_memberships_active_owner_per_org",
        )

        persist(
            factory,
            MEMBERSHIPS.update()
            .where(MEMBERSHIPS.c.membership_id == membership_ids[0])
            .values(is_active=False),
        )
        rows = read_identity_state(factory)[2]
        assert len(rows) == 2
        assert all(row[4] is False for row in rows)
