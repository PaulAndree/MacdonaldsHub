"""The consumer: one attempt, 30 s apart, recorded first, never repeated (RF-11, RF-13, MAIL-01..11)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.adapters.db.email_sending import SqlSendingRepository
from app.adapters.db.engine import make_engine
from app.migrate import run
from app.services.email_sending import EmailConsumer
from tests.integration.mail_helpers import (
    REFUSED,
    TEST_RECIPIENT,
    UNVERIFIED,
    FakeTransport,
    add_email,
    age_last_start,
    pause,
    resume,
    row,
)

pytestmark = pytest.mark.integration

SENDER = "institutional@example.test"


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def consumer(engine, transport, unavailable=None, recipient=TEST_RECIPIENT):  # type: ignore[no-untyped-def]
    return EmailConsumer(
        SqlSendingRepository(engine),
        transport,
        sender=SENDER,
        authorized_recipient=recipient,
        unavailable=lambda: unavailable,
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


# --- starting: paused, interval, order (MAIL-01, MAIL-02) ------------------------------------------------------


def test_a_new_environment_sends_nothing_until_it_is_resumed(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    transport = FakeTransport()
    consumer(engine, transport).tick()
    assert transport.sent == [] and states(engine) == {"A-1": "pending"}


def test_once_resumed_the_oldest_email_is_sent_alone(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "NEW", seconds_old=10)
    add_email(engine, "OLD", seconds_old=500)
    resume(engine)
    transport = FakeTransport()
    consumer(engine, transport).tick()
    assert [m.body for m in transport.sent] == ["Incidente OLD para su reclamación."]
    assert states(engine) == {"OLD": "sent", "NEW": "pending"}


def test_the_message_has_the_stored_text_and_only_the_order_id(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "AB-1029x")
    resume(engine)
    transport = FakeTransport()
    consumer(engine, transport).tick()
    (message,) = transport.sent
    assert (message.sender, message.recipient) == (SENDER, TEST_RECIPIENT)
    assert message.subject == "Reclamación de incidente"
    assert message.body == "Incidente AB-1029x para su reclamación."


def test_the_start_is_recorded_before_the_mail_service_is_called(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    seen: list[tuple[str, object]] = []

    def look(_message: object) -> None:
        seen.append(tuple(row(engine, "SELECT state, started_at IS NOT NULL FROM outbox")))  # type: ignore[arg-type]

    consumer(engine, FakeTransport(on_send=look)).tick()
    assert seen == [("sending", True)]


@pytest.mark.parametrize(
    ("ago", "second_sent"), [(0, False), (10, False), (29, False), (31, True), (300, True)]
)
def test_the_next_attempt_waits_30_seconds_from_the_previous_start(
    engine, ago: float, second_sent: bool
) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    transport = FakeTransport()
    c = consumer(engine, transport)
    c.tick()
    age_last_start(engine, ago)
    c.tick()
    assert len(transport.sent) == (2 if second_sent else 1)


def test_the_interval_also_counts_after_a_failed_attempt(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    transport = FakeTransport(outcome=REFUSED)
    c = consumer(engine, transport)
    c.tick()
    c.tick()  # right after a failure: still waits
    assert len(transport.sent) == 1 and states(engine) == {"A-1": "error", "A-2": "pending"}
    age_last_start(engine, 31)
    c.tick()
    assert len(transport.sent) == 2


def test_pausing_stops_new_attempts_but_not_the_one_in_progress(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    transport = FakeTransport(on_send=lambda _m: pause(engine))  # paused while A-1 is being sent
    c = consumer(engine, transport)
    c.tick()
    assert states(engine) == {"A-1": "sent", "A-2": "pending"}  # the started attempt finished
    age_last_start(engine, 100)
    c.tick()
    assert len(transport.sent) == 1  # nothing else starts while paused
    resume(engine)
    c.tick()
    assert len(transport.sent) == 2


# --- nothing else is ever sent --------------------------------------------------------------------------------------


def test_glovo_has_no_attempt(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "G-1", provider="glovo")  # not something the system creates, but never sent
    resume(engine)
    transport = FakeTransport()
    consumer(engine, transport).tick()
    assert transport.sent == [] and states(engine) == {"G-1": "pending"}


def test_when_sending_is_unavailable_nothing_starts_and_nothing_turns_into_an_error(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    transport = FakeTransport()
    c = consumer(engine, transport, unavailable="No hay un destinatario de prueba configurado.")
    for _ in range(3):
        c.tick()
    assert transport.sent == [] and states(engine) == {"A-1": "pending"}
    assert row(engine, "SELECT last_started_at FROM mail_control")[0] is None


def test_a_recipient_that_is_not_authorized_ends_in_error_without_calling_the_service(
    engine,
) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", recipient="uber@real-provider.example", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    transport = FakeTransport()
    c = consumer(engine, transport)
    c.tick()
    assert transport.sent == []
    state, kind, reason = row(
        engine,
        "SELECT o.state, o.error_kind, o.reason FROM outbox o JOIN incident i ON i.id = o.incident_id WHERE i.order_id = 'A-1'",
    )
    assert (state, kind) == ("error", "send_failed") and "no autorizado" in reason
    assert row(engine, "SELECT state FROM incident WHERE order_id = 'A-1'")[0] == "send_error"
    # It never started an attempt, so the next email can go without waiting.
    c.tick()
    assert [m.recipient for m in transport.sent] == [TEST_RECIPIENT]


def test_an_email_whose_recipient_is_no_longer_the_authorized_one_is_not_sent(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    transport = FakeTransport()
    consumer(engine, transport, recipient="someone-else@example.test").tick()
    assert transport.sent == []  # the stored recipient is no longer the authorized one: not sent
    assert states(engine) == {"A-1": "error"}


# --- results (MAIL-06, E-10) ------------------------------------------------------------------------------------------


def test_a_send_that_finishes_without_error_is_recorded_as_sent_and_claims_the_incident(
    engine,
) -> None:  # type: ignore[no-untyped-def]
    ids = add_email(engine, "A-1")
    resume(engine)
    consumer(engine, FakeTransport()).tick()
    state, started, finished, reason, kind = row(
        engine, "SELECT state, started_at, finished_at, reason, error_kind FROM outbox"
    )
    assert state == "sent" and started is not None and finished >= started
    assert (reason, kind) == (None, None)
    status, claim_date = row(engine, "SELECT state, claim_date FROM incident")
    assert status == "claimed"
    assert claim_date == datetime.now(ZoneInfo("Europe/Madrid")).date()
    with engine.connect() as conn:
        history = conn.execute(
            text(
                "SELECT actor, kind, field, previous, new FROM incident_history WHERE incident_id = :i ORDER BY seq"
            ),
            {"i": ids["incident"]},
        ).all()
    assert history == [
        ("system", "email_result", "status", "pending_send", "claimed"),
        ("system", "email_result", "claimDate", None, str(claim_date)),
    ]


def test_a_refusal_is_an_error_with_its_reason_and_the_incident_fails_for_good(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    consumer(engine, FakeTransport(outcome=REFUSED)).tick()
    state, kind, reason = row(engine, "SELECT state, error_kind, reason FROM outbox")
    assert (state, kind, reason) == ("error", "send_failed", str(REFUSED))
    assert row(engine, "SELECT state FROM incident")[0] == "send_error"
    history = row(engine, "SELECT kind, field, new, reason FROM incident_history")
    assert tuple(history) == ("email_result", "status", "send_error", str(REFUSED))


def test_an_unverifiable_outcome_is_an_error_of_that_kind(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    consumer(engine, FakeTransport(outcome=UNVERIFIED)).tick()
    assert tuple(row(engine, "SELECT state, error_kind FROM outbox")) == (
        "error",
        "interrupted_unverified",
    )


def test_an_unexpected_failure_is_treated_as_unverified_not_as_a_clean_refusal(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1")
    resume(engine)
    consumer(engine, FakeTransport(outcome=RuntimeError("bug"))).tick()
    assert tuple(row(engine, "SELECT state, error_kind FROM outbox")) == (
        "error",
        "interrupted_unverified",
    )


def test_the_attempt_and_its_result_are_audited_without_secrets_or_content(engine) -> None:  # type: ignore[no-untyped-def]
    ids = add_email(engine, "A-1")
    resume(engine)
    consumer(engine, FakeTransport()).tick()
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT actor, operation, object_type, object_id, outcome, details::text FROM audit_log WHERE object_type = 'email' ORDER BY id"
            )
        ).all()
    assert [(r[0], r[1], r[3], r[4]) for r in rows] == [
        ("system:worker", "email.attempt_started", ids["email"], "success"),
        ("system:worker", "email.sent", ids["email"], "success"),
    ]
    dump = " ".join(r[5] or "" for r in rows)
    assert TEST_RECIPIENT not in dump and "para su reclamación" not in dump


# --- batches complete when every email has ended (MAIL-08) ----------------------------------------------------------------


def test_a_batch_completes_when_its_last_email_ends_with_failures_kept_apart(engine) -> None:  # type: ignore[no-untyped-def]
    first = add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", batch=first["batch"], seconds_old=50)
    resume(engine)
    transport = FakeTransport()
    c = consumer(engine, transport)
    c.tick()
    assert row(engine, "SELECT state FROM batch")[0] == "confirmed"  # one email is still pending
    transport.outcome = REFUSED
    age_last_start(engine, 31)
    c.tick()
    assert row(engine, "SELECT state FROM batch")[0] == "completed"
    assert states(engine) == {"A-1": "sent", "A-2": "error"}


def test_the_email_of_a_manual_entry_has_no_batch_and_is_sent(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "M-1", batch=None)
    resume(engine)
    transport = FakeTransport()
    consumer(engine, transport).tick()
    assert len(transport.sent) == 1 and states(engine) == {"M-1": "sent"}


# --- no second attempt, ever (RN-12) -----------------------------------------------------------------------------------------


def test_the_service_is_called_exactly_once_per_email_whatever_happens_afterwards(engine) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "OK", seconds_old=300)
    add_email(engine, "BAD", seconds_old=200)
    add_email(engine, "LOST", seconds_old=100)
    resume(engine)
    transport = FakeTransport()
    c = consumer(engine, transport)
    c.tick()
    transport.outcome = REFUSED
    age_last_start(engine, 31)
    c.tick()
    transport.outcome = UNVERIFIED
    age_last_start(engine, 31)
    c.tick()
    transport.outcome = None
    for _ in range(10):  # restarts, pauses, resumes, time passing: nothing sends them again
        age_last_start(engine, 31)
        pause(engine)
        resume(engine)
        consumer(engine, transport).tick()
    assert [m.body for m in transport.sent] == [
        "Incidente OK para su reclamación.",
        "Incidente BAD para su reclamación.",
        "Incidente LOST para su reclamación.",
    ]
    assert states(engine) == {"OK": "sent", "BAD": "error", "LOST": "error"}


# --- restarts and overlapping workers (MAIL-03, MAIL-04, MAIL-07) ---------------------------------------------------------


def test_an_attempt_left_unfinished_ends_in_error_and_is_not_sent_again(engine) -> None:  # type: ignore[no-untyped-def]
    ids = add_email(engine, "LOST", seconds_old=100)
    add_email(engine, "NEXT", seconds_old=50)
    resume(engine)
    with engine.begin() as conn:  # the worker died after recording the start
        conn.execute(
            text(
                "UPDATE outbox SET state = 'sending', started_at = now() - interval '10 seconds' WHERE id = :e"
            ),
            {"e": ids["email"]},
        )
        conn.execute(
            text("UPDATE mail_control SET last_started_at = now() - interval '10 seconds'")
        )
    transport = FakeTransport()
    c = consumer(engine, transport)
    c.tick()
    state, kind, reason = row(
        engine, "SELECT state, error_kind, reason FROM outbox WHERE id = :e", e=ids["email"]
    )
    assert (state, kind) == ("error", "interrupted_unverified") and "no se pudo verificar" in reason
    assert (
        row(engine, "SELECT state FROM incident WHERE id = :i", i=ids["incident"])[0]
        == "send_error"
    )
    assert (
        transport.sent == []
    )  # the lost one is not sent again, and the next one waits for the interval
    age_last_start(engine, 31)
    c.tick()
    assert [m.body for m in transport.sent] == ["Incidente NEXT para su reclamación."]


def test_a_result_that_arrives_after_the_recovery_changes_nothing(engine) -> None:  # type: ignore[no-untyped-def]
    ids = add_email(engine, "A-1")
    resume(engine)
    repository = SqlSendingRepository(engine)
    with engine.begin() as conn:
        conn.execute(text("UPDATE outbox SET state = 'sending', started_at = now()"))
    repository.recover_interrupted()  # another worker took over and ended it
    assert repository.finish_sent(ids["email"] or "") is False
    assert tuple(row(engine, "SELECT state, error_kind FROM outbox")) == (
        "error",
        "interrupted_unverified",
    )
    assert row(engine, "SELECT state FROM incident")[0] == "send_error"


def test_simultaneous_claims_start_one_attempt_only(engine) -> None:  # type: ignore[no-untyped-def]
    """Whoever asks, the control row serializes the starts (the owner lock already keeps one worker)."""
    add_email(engine, "A-1")
    resume(engine)
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(
            pool.map(lambda _: SqlSendingRepository(engine).claim(TEST_RECIPIENT), range(6))
        )
    assert len([c for c in claims if c is not None]) == 1
    assert states(engine) == {"A-1": "sending"}


def test_simultaneous_claims_with_two_pending_emails_still_respect_the_global_interval(
    engine,
) -> None:  # type: ignore[no-untyped-def]
    add_email(engine, "A-1", seconds_old=100)
    add_email(engine, "A-2", seconds_old=50)
    resume(engine)
    with ThreadPoolExecutor(max_workers=6) as pool:
        claims = list(
            pool.map(lambda _: SqlSendingRepository(engine).claim(TEST_RECIPIENT), range(6))
        )
    assert len([c for c in claims if c is not None]) == 1  # the second one waits 30 s whoever asks
    assert sorted(states(engine).values()) == ["pending", "sending"]
