from uuid import uuid4

import pytest
from sqlalchemy import text

from opsdesk.db.session import create_session_factory, session_scope


@pytest.mark.integration
def test_committed_probe_is_visible_and_cleaned(probe_scope, integration_engine):
    marker = uuid4().hex

    with probe_scope() as factory:
        with session_scope(factory) as session:
            session.execute(
                text("INSERT INTO public.integration_probe (marker) VALUES (:marker)"),
                {"marker": marker},
            )
            session.commit()

        with session_scope(factory) as session:
            result = session.execute(
                text(
                    "SELECT marker FROM public.integration_probe WHERE marker = :marker"
                ),
                {"marker": marker},
            ).scalar_one_or_none()

            assert result == marker

    outside_factory = create_session_factory(integration_engine)
    with session_scope(outside_factory) as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM public.integration_probe")
        ).scalar_one()
        assert count == 0

    with probe_scope() as factory2:
        with session_scope(factory2) as session:
            count_new_scope = session.execute(
                text("SELECT COUNT(*) FROM public.integration_probe")
            ).scalar_one()
            assert count_new_scope == 0


@pytest.mark.integration
def test_committed_probe_is_cleaned_after_exception(probe_scope, integration_engine):
    marker = uuid4().hex

    with pytest.raises(RuntimeError, match="Synthetic scope error"):
        with probe_scope() as factory:
            with session_scope(factory) as session:
                session.execute(
                    text(
                        "INSERT INTO public.integration_probe (marker) VALUES (:marker)"
                    ),
                    {"marker": marker},
                )
                session.commit()
                raise RuntimeError("Synthetic scope error")

    outside_factory = create_session_factory(integration_engine)
    with session_scope(outside_factory) as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM public.integration_probe")
        ).scalar_one()
        assert count == 0


@pytest.mark.integration
def test_uncommitted_probe_is_rolled_back_when_session_closes(probe_scope):
    marker = uuid4().hex

    with probe_scope() as factory:
        with session_scope(factory) as session:
            session.execute(
                text("INSERT INTO public.integration_probe (marker) VALUES (:marker)"),
                {"marker": marker},
            )

        with session_scope(factory) as session:
            result = session.execute(
                text(
                    "SELECT marker FROM public.integration_probe WHERE marker = :marker"
                ),
                {"marker": marker},
            ).scalar_one_or_none()

            assert result is None
