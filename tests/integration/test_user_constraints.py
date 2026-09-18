import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from opsdesk.db.models import UserRow
from opsdesk.db.session import session_scope


@pytest.mark.integration
@pytest.mark.parametrize("existing_is_active", [True, False])
def test_duplicate_email_is_rejected(identity_scope, existing_is_active):
    email = "duplicate@example.com"

    with identity_scope() as factory:
        with session_scope(factory) as session:
            original = UserRow(
                email=email,
                password_hash="original-test-hash-placeholder",
                is_active=existing_is_active,
            )
            session.add(original)
            session.commit()
            original_id = original.user_id

        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(factory) as session:
                session.add(
                    UserRow(
                        email=email,
                        password_hash="duplicate-test-hash-placeholder",
                    )
                )
                session.commit()

        assert exc_info.value.orig.sqlstate == "23505"
        assert exc_info.value.orig.diag.constraint_name == "uq_users_email"

        with session_scope(factory) as session:
            rows = session.execute(
                text(
                    "SELECT user_id, email, password_hash, is_active FROM public.users"
                )
            ).all()

            assert [tuple(row) for row in rows] == [
                (
                    original_id,
                    email,
                    "original-test-hash-placeholder",
                    existing_is_active,
                )
            ]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("email", "expected_constraints"),
    [
        ("User@example.com", {"ck_users_email_lowercase"}),
        ("fürkan@example.com", {"ck_users_email_ascii_nonspace"}),
        ("user name@example.com", {"ck_users_email_ascii_nonspace"}),
        ("user@example.com ", {"ck_users_email_ascii_nonspace"}),
        ("user\t@example.com", {"ck_users_email_ascii_nonspace"}),
        ("a" * 255, {"ck_users_email_length"}),
        (
            "",
            {"ck_users_email_length", "ck_users_email_ascii_nonspace"},
        ),
    ],
)
def test_invalid_email_storage_is_rejected(identity_scope, email, expected_constraints):
    with identity_scope() as factory:
        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(factory) as session:
                session.add(
                    UserRow(
                        email=email,
                        password_hash="test-only-hash-placeholder",
                    )
                )
                session.commit()

        assert exc_info.value.orig.sqlstate == "23514"
        assert exc_info.value.orig.diag.constraint_name in expected_constraints

        with session_scope(factory) as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM public.users")
            ).scalar_one()
            assert count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    "email",
    [
        "a",
        "a" * 254,
        "furkan+support@example.com",
        "fur.kan@example.com",
    ],
)
def test_accepted_email_storage_and_user_defaults(identity_scope, email):
    with identity_scope() as factory:
        with session_scope(factory) as session:
            user = UserRow(
                email=email,
                password_hash="test-only-hash-placeholder",
            )
            session.add(user)
            session.commit()
            user_id = user.user_id

        with session_scope(factory) as session:
            row = session.execute(
                text(
                    "SELECT user_id, email, is_active "
                    "FROM public.users WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            ).one()

            assert row.user_id > 0
            assert row.email == email
            assert row.is_active is True


@pytest.mark.integration
@pytest.mark.parametrize("column_name", ["email", "password_hash", "is_active"])
def test_required_user_fields_reject_null(identity_scope, column_name):
    values = {
        "email": "required-fields@example.com",
        "password_hash": "test-only-hash-placeholder",
        "is_active": True,
    }
    values[column_name] = None

    with identity_scope() as factory:
        with pytest.raises(IntegrityError) as exc_info:
            with session_scope(factory) as session:
                session.execute(
                    text(
                        "INSERT INTO public.users "
                        "(email, password_hash, is_active) "
                        "VALUES (:email, :password_hash, :is_active)"
                    ),
                    values,
                )
                session.commit()

        assert exc_info.value.orig.sqlstate == "23502"
        assert exc_info.value.orig.diag.table_name == "users"
        assert exc_info.value.orig.diag.column_name == column_name

        with session_scope(factory) as session:
            count = session.execute(
                text("SELECT COUNT(*) FROM public.users")
            ).scalar_one()
            assert count == 0
