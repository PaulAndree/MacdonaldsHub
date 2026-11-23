"""The audit record joins the caller's transaction: it exists with the change or not at all."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.adapters.db.audit import SqlAuditLog
from app.adapters.db.engine import make_engine
from app.migrate import run
from app.services.audit import Auditor

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def rows(engine):  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT actor, operation, object_type, object_id, outcome, details FROM audit_log")
        ).all()


def test_a_record_is_stored_with_the_transaction(engine) -> None:  # type: ignore[no-untyped-def]
    with engine.begin() as conn:
        audit = Auditor(SqlAuditLog(conn))
        audit.record("ana", "batch.confirm", "batch", "b-1", "success", {"n": 3})
    assert rows(engine) == [("ana", "batch.confirm", "batch", "b-1", "success", {"n": 3})]


def test_the_record_rolls_back_with_the_transaction(engine) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(RuntimeError), engine.begin() as conn:
        Auditor(SqlAuditLog(conn)).record("ana", "batch.confirm", "batch", "b-1", "success")
        raise RuntimeError("the confirmation fails afterwards")
    assert rows(engine) == []


def test_the_stored_instant_is_the_one_of_the_clock(engine) -> None:  # type: ignore[no-untyped-def]
    instant = datetime(2026, 11, 23, 10, 30, tzinfo=UTC)
    with engine.begin() as conn:
        audit = Auditor(SqlAuditLog(conn), clock=lambda: instant)
        audit.record("ana", "x", "batch", None, "success")
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT at FROM audit_log")).scalar()
    assert stored == instant
