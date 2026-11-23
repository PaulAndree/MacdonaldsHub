"""The audit trail can only grow (RF-19): the database refuses to change or remove records."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.adapters.db.engine import make_engine
from app.migrate import run

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    with eng.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_log (actor, operation, object_type, object_id, outcome) "
                "VALUES ('ana', 'batch.confirm', 'batch', 'b-1', 'success')"
            )
        )
    yield eng
    eng.dispose()


def test_inserting_and_reading_work(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO audit_log (actor, operation, object_type, outcome) "
                "VALUES ('system:worker', 'batch.process', 'batch', 'success')"
            )
        )
        count = conn.execute(text("SELECT count(*) FROM audit_log")).scalar()
    assert count == 2


def test_updating_a_record_is_refused(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("UPDATE audit_log SET outcome = 'failure'"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT outcome FROM audit_log")).scalar() == "success"


def test_deleting_a_record_is_refused(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_log"))
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar() == 1


def test_truncating_the_table_is_refused(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("TRUNCATE audit_log"))


def test_the_migration_can_be_reverted(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("downgrade", database_url, "0002")
    with engine.begin() as conn:
        conn.execute(text("UPDATE audit_log SET outcome = 'failure'"))
    run("upgrade", database_url)
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as conn:
        conn.execute(text("DELETE FROM audit_log"))
