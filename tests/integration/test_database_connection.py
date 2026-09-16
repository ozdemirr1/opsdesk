import pytest
from sqlalchemy import text

from opsdesk.db.session import create_session_factory, session_scope


@pytest.mark.integration
def test_connects_to_expected_database_and_role(integration_engine):
    factory = create_session_factory(integration_engine)

    with session_scope(factory) as session:
        result = session.execute(
            text(
                "SELECT current_database(), current_user, "
                "host(inet_server_addr()), inet_server_port()"
            )
        ).one()

    assert result == (
        "opsdesk_product_test",
        "opsdesk_product_test_runner",
        "127.0.0.1",
        5432,
    )


@pytest.mark.integration
def test_session_returns_connection_to_pool(integration_engine):
    factory = create_session_factory(integration_engine)

    assert integration_engine.pool.checkedout() == 0

    with session_scope(factory) as session:
        result = session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
        assert integration_engine.pool.checkedout() == 1

    assert integration_engine.pool.checkedout() == 0


@pytest.mark.integration
def test_session_returns_connection_to_pool_after_exception(integration_engine):
    factory = create_session_factory(integration_engine)

    assert integration_engine.pool.checkedout() == 0

    with pytest.raises(RuntimeError, match="Synthetic session failure"):
        with session_scope(factory) as session:
            result = session.execute(text("SELECT 1")).scalar_one()
            assert result == 1
            assert integration_engine.pool.checkedout() == 1
            raise RuntimeError("Synthetic session failure")

    assert integration_engine.pool.checkedout() == 0
