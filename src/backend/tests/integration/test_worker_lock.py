import pytest
from sqlalchemy import text

from app.adapters.db.advisory_lock import AdvisoryLock
from app.adapters.db.engine import make_engine

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    yield eng
    eng.dispose()


def test_only_one_instance_owns_the_lock(engine) -> None:  # type: ignore[no-untyped-def]  # BASE-07
    a, b = AdvisoryLock(engine), AdvisoryLock(engine)
    try:
        assert a.try_acquire() is True
        assert b.try_acquire() is False  # overlapping revision does not get ownership
        assert a.still_held() is True and b.held is False
    finally:
        a.release()
        b.release()


def test_acquire_is_idempotent_for_the_owner(engine) -> None:  # type: ignore[no-untyped-def]
    a = AdvisoryLock(engine)
    try:
        assert a.try_acquire() and a.try_acquire()
    finally:
        a.release()


def test_other_instance_takes_over_after_clean_release(engine) -> None:  # type: ignore[no-untyped-def]
    a, b = AdvisoryLock(engine), AdvisoryLock(engine)
    try:
        assert a.try_acquire()
        assert not b.try_acquire()
        a.release()
        assert b.try_acquire()
    finally:
        a.release()
        b.release()


def test_takeover_after_owner_connection_is_killed(engine) -> None:  # type: ignore[no-untyped-def]
    a, b = AdvisoryLock(engine), AdvisoryLock(engine)
    try:
        assert a.try_acquire()
        pid = a.backend_pid()
        assert not b.try_acquire()
        with engine.connect() as admin:
            admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": pid})
            admin.commit()
        assert a.still_held() is False  # the owner notices it lost ownership
        assert b.try_acquire() is True  # and the standby takes over
    finally:
        a.release()
        b.release()


def test_two_workers_only_one_does_the_work(engine, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from opentelemetry import trace

    from app.worker.loop import Worker

    done: list[str] = []
    w1 = Worker(
        AdvisoryLock(engine),
        trace.get_tracer("t"),
        tmp_path / "1.json",
        lambda: done.append("w1"),
        "w1",
    )
    w2 = Worker(
        AdvisoryLock(engine),
        trace.get_tracer("t"),
        tmp_path / "2.json",
        lambda: done.append("w2"),
        "w2",
    )
    try:
        for _ in range(3):
            w1.tick()
            w2.tick()
        assert (w1.state, w2.state) == ("owner", "standby")
        assert done == ["w1", "w1", "w1"]

        w1.shutdown()  # old revision stops
        w2.tick()
        assert w2.state == "owner" and done[-1] == "w2"
    finally:
        w1.shutdown()
        w2.shutdown()
