"""The control row of the sender: paused from the start, with the last start of an attempt (RF-14)."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.adapters.db.engine import make_engine
from app.migrate import run

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def test_there_is_exactly_one_control_row_and_it_is_paused(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT paused, paused_at, last_started_at FROM mail_control")
        ).all()
    assert rows == [(True, None, None)]  # a new environment sends nothing until it is resumed


def test_a_second_row_is_refused(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text("INSERT INTO mail_control (id) VALUES (2)"))


def test_the_pending_queue_has_its_index(engine) -> None:  # type: ignore[no-untyped-def]
    names = {i["name"] for i in inspect(engine).get_indexes("outbox")}
    assert "ix_outbox_pending_order" in names


def test_the_migration_goes_down_and_up(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("downgrade", database_url, "0009")
    assert "mail_control" not in inspect(engine).get_table_names()
    run("upgrade", database_url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT paused FROM mail_control")).scalar() is True
