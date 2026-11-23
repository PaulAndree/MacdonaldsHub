"""The sender inside the worker: one owner, restarts and overlapping revisions (MAIL-03, MAIL-04)."""

import pytest
from opentelemetry import trace
from sqlalchemy import text

from app.adapters.db.advisory_lock import AdvisoryLock
from app.adapters.db.email_sending import SqlSendingRepository
from app.adapters.db.engine import make_engine
from app.migrate import run
from app.services.email_sending import EmailConsumer
from app.worker.loop import Worker
from tests.integration.mail_helpers import (
    TEST_RECIPIENT,
    FakeTransport,
    add_email,
    age_last_start,
    resume,
    row,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def worker(engine, transport, tmp_path, name: str):  # type: ignore[no-untyped-def]
    consumer = EmailConsumer(
        SqlSendingRepository(engine),
        transport,
        sender="institutional@example.test",
        authorized_recipient=TEST_RECIPIENT,
        unavailable=lambda: None,
    )
    return Worker(
        AdvisoryLock(engine),
        trace.get_tracer("test"),
        tmp_path / f"{name}.json",
        work=lambda: consumer.tick(),
        instance_id=name,
    )


def states(engine) -> dict[str, str]:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        return dict(
            conn.execute(
                text(
                    "SELECT i.order_id, o.state FROM outbox o JOIN incident i ON i.id = o.incident_id"
                )
            ).all()
        )


def test_two_overlapping_revisions_send_once_and_keep_the_interval(engine, tmp_path) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    transport = FakeTransport()
    old = worker(engine, transport, tmp_path, "old")
    new = worker(engine, transport, tmp_path, "new")
    try:
        for _ in range(3):
            assert (old.tick(), new.tick()) == ("owner", "standby")
        assert len(transport.sent) == 1  # one owner, and the second email waits 30 s
        age_last_start(engine, 31)
        old.tick()
        new.tick()
        assert len(transport.sent) == 2
    finally:
        old.shutdown()
        new.shutdown()


def test_a_standby_does_not_send_while_the_owner_lives(engine, tmp_path) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    transport = FakeTransport()
    owner = worker(engine, FakeTransport(), tmp_path, "owner")
    standby = worker(engine, transport, tmp_path, "standby")
    try:
        owner.tick()  # takes the lock and sends
        standby.tick()
        assert transport.sent == []
    finally:
        owner.shutdown()
        standby.shutdown()


def test_when_the_owner_dies_mid_send_the_new_owner_ends_it_in_error_and_does_not_resend(
    engine, tmp_path
) -> None:  # type: ignore[no-untyped-def]
    first = add_email(engine, "LOST", seconds_old=100)
    add_email(engine, "NEXT", seconds_old=50)
    resume(engine)
    transport = FakeTransport()
    dying = worker(engine, FakeTransport(), tmp_path, "dying")
    standby = worker(engine, transport, tmp_path, "standby")
    try:
        assert dying.tick() == "owner"  # it sent LOST
        # Pretend that send never got recorded: it died after the start and before the result.
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE outbox SET state = 'sending', finished_at = NULL, reason = NULL, error_kind = NULL WHERE id = :e"
                ),
                {"e": first["email"]},
            )
            conn.execute(
                text("UPDATE incident SET state = 'pending_send', claim_date = NULL WHERE id = :i"),
                {"i": first["incident"]},
            )
            conn.execute(
                text("UPDATE mail_control SET last_started_at = now() - interval '10 seconds'")
            )
        pid = dying._lock.backend_pid()  # type: ignore[attr-defined]
        with engine.connect() as admin:
            admin.execute(text("SELECT pg_terminate_backend(:p)"), {"p": pid})
            admin.commit()
        assert standby.tick() == "owner"  # it took over
        state, kind = row(
            engine, "SELECT state, error_kind FROM outbox WHERE id = :e", e=first["email"]
        )
        assert (state, kind) == ("error", "interrupted_unverified")
        assert transport.sent == []  # LOST is not sent again, and NEXT waits for the interval
        age_last_start(engine, 31)
        standby.tick()
        assert [m.body for m in transport.sent] == ["Incidente NEXT para su reclamación."]
    finally:
        dying.shutdown()
        standby.shutdown()
