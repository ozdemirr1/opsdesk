import pytest

from opsdesk.db.guards import validate_test_target


def test_validate_test_target_accepts_exact_match():
    validate_test_target(host="127.0.0.1", port=5432, database="opsdesk_product_test")


@pytest.mark.parametrize(
    "database",
    ["opsdesk_product_dev", "opsdesk_dev", "opsdesk_test"],
)
def test_validate_test_target_rejects_disallowed_databases(database):
    with pytest.raises(
        ValueError, match=r"^Unsafe integration-test database target\.$"
    ):
        validate_test_target(host="127.0.0.1", port=5432, database=database)


def test_validate_test_target_rejects_another_test():
    with pytest.raises(
        ValueError, match=r"^Unsafe integration-test database target\.$"
    ):
        validate_test_target(host="127.0.0.1", port=5432, database="another_test")


def test_validate_test_target_rejects_trailing_space():
    with pytest.raises(
        ValueError, match=r"^Unsafe integration-test database target\.$"
    ):
        validate_test_target(
            host="127.0.0.1", port=5432, database="opsdesk_product_test "
        )


def test_validate_test_target_rejects_localhost():
    with pytest.raises(
        ValueError, match=r"^Unsafe integration-test database target\.$"
    ):
        validate_test_target(
            host="localhost", port=5432, database="opsdesk_product_test"
        )


def test_validate_test_target_rejects_different_port():
    with pytest.raises(
        ValueError, match=r"^Unsafe integration-test database target\.$"
    ):
        validate_test_target(
            host="127.0.0.1", port=5433, database="opsdesk_product_test"
        )
