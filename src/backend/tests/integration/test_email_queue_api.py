"""The queue, pause and resume (RF-14, MAIL-02, MAIL-09), through the API with real PostgreSQL."""

from typing import Any

import pytest
from sqlalchemy import text

from tests.integration.batch_helpers import ADMIN
from tests.integration.mail_helpers import add_email, age_last_start, resume
from tests.integration.test_api import principal_headers

pytestmark = pytest.mark.integration

MANAGER = "manager@example.test"


@pytest.fixture
def api(client):  # type: ignore[no-untyped-def]
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) "
                "VALUES (gen_random_uuid(), :m, :m, 'global_manager')"
            ),
            {"m": MANAGER},
        )
    return client


def get(api: Any, who: str = ADMIN, **params: Any) -> Any:
    return api.get("/api/email-queue", params=params, headers=principal_headers(who))


def post(api: Any, action: str, who: str = ADMIN) -> Any:
    return api.post(f"/api/email-queue/{action}", headers=principal_headers(who))


def make_sendable(api: Any) -> None:
    settings = api.app.state.settings
    settings.smtp_host, settings.smtp_from = "mailpit", "institutional@example.test"


def end(
    api: Any, email: str, state: str, kind: str | None = None, reason: str | None = None
) -> None:
    with api.engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE outbox SET state = :s, error_kind = :k, reason = :r, "
                "started_at = now() - interval '1 minute', finished_at = now() WHERE id = :e"
            ),
            {"s": state, "k": kind, "r": reason, "e": email},
        )


# --- a new environment ------------------------------------------------------------------------------------


def test_a_new_environment_is_paused_and_empty(api) -> None:  # type: ignore[no-untyped-def]
    body = get(api).json()
    assert body["status"]["paused"] is True and body["status"]["pausedAt"] is None
    assert body["status"]["inFlight"] == 0
    assert (body["minIntervalSeconds"], body["attemptsPerEmail"]) == (30, 1)
    assert body["totals"] == {"pending": 0, "sending": 0, "sent": 0, "error": 0}
    assert (body["batches"], body["items"], body["total"], body["nextEligibleAt"]) == (
        [],
        [],
        0,
        None,
    )


# --- pause and resume (MAIL-02, MAIL-09) ---------------------------------------------------------------------


def test_resuming_and_pausing_are_persistent_and_say_when(api) -> None:  # type: ignore[no-untyped-def]
    resumed = post(api, "resume")
    assert resumed.status_code == 200 and resumed.json()["paused"] is False
    assert resumed.json()["pausedAt"] is None
    assert get(api).json()["status"]["paused"] is False
    paused = post(api, "pause")
    assert paused.json()["paused"] is True and paused.json()["pausedAt"] is not None
    assert get(api).json()["status"]["paused"] is True


def test_pausing_does_not_touch_an_attempt_in_progress_or_any_email(api) -> None:  # type: ignore[no-untyped-def]
    ids = add_email(api.engine, "A-1")
    add_email(api.engine, "A-2")
    resume(api.engine)
    with api.engine.begin() as conn:
        conn.execute(
            text("UPDATE outbox SET state = 'sending', started_at = now() WHERE id = :e"),
            {"e": ids["email"]},
        )
    paused = post(api, "pause").json()
    assert paused["inFlight"] == 1
    with api.engine.connect() as conn:
        states = sorted(r[0] for r in conn.execute(text("SELECT state FROM outbox")))
    assert states == ["pending", "sending"]  # nothing was cancelled or changed


def test_pause_and_resume_are_audited_with_the_user(api) -> None:  # type: ignore[no-untyped-def]
    post(api, "resume")
    post(api, "pause")
    with api.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT actor, operation, details::text FROM audit_log WHERE object_type = 'mail_queue' ORDER BY id"
            )
        ).all()
    assert [(r[0], r[1]) for r in rows] == [(ADMIN, "queue.resume"), (ADMIN, "queue.pause")]
    assert '"paused": false' in rows[0][2] and '"paused": true' in rows[1][2]


def test_a_user_without_the_permission_cannot_pause_resume_or_even_read_and_nothing_changes(
    api,
) -> None:  # type: ignore[no-untyped-def]
    for action in ("pause", "resume"):
        assert post(api, action, who=MANAGER).status_code == 403
    assert get(api, who=MANAGER).status_code == 403
    assert api.get("/api/email-queue").status_code == 401
    assert get(api).json()["status"]["paused"] is True  # still the initial state
    with api.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE object_type = 'mail_queue'")
            ).scalar()
            == 0
        )


# --- reading the queue ---------------------------------------------------------------------------------------------


def seeded(api: Any) -> dict[str, dict[str, str | None]]:
    first = add_email(api.engine, "A-1", seconds_old=500)
    second = add_email(
        api.engine, "A-2", batch=first["batch"], seconds_old=400, provider="just eat"
    )
    third = add_email(api.engine, "A-3", batch=first["batch"], seconds_old=300)
    manual = add_email(api.engine, "M-1", batch=None, seconds_old=200)
    end(api, first["email"] or "", "sent")
    end(
        api,
        second["email"] or "",
        "error",
        "send_failed",
        "El servidor rechazó el destinatario: 550 no existe",
    )
    return {"first": first, "second": second, "third": third, "manual": manual}


def test_the_queue_has_totals_and_every_email_with_its_outcome(api) -> None:  # type: ignore[no-untyped-def]
    ids = seeded(api)
    body = get(api).json()
    assert body["totals"] == {"pending": 2, "sending": 0, "sent": 1, "error": 1}
    assert body["total"] == 4
    by_order = {i["orderId"]: i for i in body["items"]}
    assert by_order["A-1"]["state"] == "sent" and by_order["A-1"]["finishedAt"] is not None
    assert by_order["A-1"]["recipient"] == {"kind": "test", "label": "Destinatario de prueba"}
    failed = by_order["A-2"]
    assert (failed["state"], failed["errorKind"]) == ("error", "send_failed")
    assert failed["reason"].startswith("El servidor rechazó") and failed["provider"] == "just eat"
    assert by_order["A-3"]["startedAt"] is None and by_order["A-3"]["reason"] is None
    assert by_order["A-1"]["incidentId"] == ids["first"]["incident"]


def test_the_email_of_a_manual_entry_has_no_batch_and_counts(api) -> None:  # type: ignore[no-untyped-def]
    seeded(api)
    items = {i["orderId"]: i for i in get(api).json()["items"]}
    assert items["M-1"]["batchId"] is None and items["A-1"]["batchId"] is not None
    assert get(api).json()["totals"]["pending"] == 2  # A-3 and M-1


def test_a_batch_is_completed_only_when_every_email_ended_and_totals_stay_apart(api) -> None:  # type: ignore[no-untyped-def]
    ids = seeded(api)
    batch = {b["batchId"]: b for b in get(api).json()["batches"]}[ids["first"]["batch"]]
    assert batch["completed"] is False and batch["totals"] == {
        "pending": 1,
        "sending": 0,
        "sent": 1,
        "error": 1,
    }
    end(api, ids["third"]["email"] or "", "sent")
    batch = {b["batchId"]: b for b in get(api).json()["batches"]}[ids["first"]["batch"]]
    assert batch["completed"] is True  # with a failure inside: completed is not "all sent"
    assert batch["totals"] == {"pending": 0, "sending": 0, "sent": 2, "error": 1}
    assert len(get(api).json()["batches"]) == 1  # manual entries belong to no batch


def test_filters_narrow_the_list_but_not_the_totals(api) -> None:  # type: ignore[no-untyped-def]
    ids = seeded(api)
    only_pending = get(api, state="pending").json()
    assert {i["orderId"] for i in only_pending["items"]} == {"A-3", "M-1"}
    assert only_pending["total"] == 2 and only_pending["totals"]["sent"] == 1
    one_batch = get(api, batchId=ids["first"]["batch"]).json()
    assert {i["orderId"] for i in one_batch["items"]} == {"A-1", "A-2", "A-3"}
    both = get(api, state="error", batchId=ids["first"]["batch"]).json()
    assert [i["orderId"] for i in both["items"]] == ["A-2"]


def test_paging_never_loses_an_email_and_states_the_total(api) -> None:  # type: ignore[no-untyped-def]
    for n in range(7):
        add_email(api.engine, f"P-{n}", seconds_old=100 - n)
    first = get(api, pageSize=3).json()
    second = get(api, pageSize=3, page=2).json()
    third = get(api, pageSize=3, page=3).json()
    assert (first["total"], len(first["items"]), len(second["items"]), len(third["items"])) == (
        7,
        3,
        3,
        1,
    )
    assert [i["orderId"] for i in first["items"] + second["items"] + third["items"]] == [
        f"P-{n}" for n in range(7)
    ]
    assert get(api, pageSize=201).status_code == 422 and get(api, state="weird").status_code == 422


def test_the_oldest_emails_come_first(api) -> None:  # type: ignore[no-untyped-def]
    add_email(api.engine, "NEW", seconds_old=10)
    add_email(api.engine, "OLD", seconds_old=900)
    assert [i["orderId"] for i in get(api).json()["items"]] == ["OLD", "NEW"]


def test_the_next_possible_start_is_30_seconds_after_the_last_one_while_running(api) -> None:  # type: ignore[no-untyped-def]
    add_email(api.engine, "A-1")
    assert get(api).json()["nextEligibleAt"] is None  # paused
    resume(api.engine)
    assert get(api).json()["nextEligibleAt"] is None  # nothing has started: it can start now
    age_last_start(api.engine, 5)
    assert get(api).json()["nextEligibleAt"] is not None
    age_last_start(api.engine, 120)
    assert get(api).json()["nextEligibleAt"] is None  # already past: it can start now


# --- when sending is unavailable ----------------------------------------------------------------------------------------


def test_the_queue_says_why_nothing_can_be_sent_and_turns_nothing_into_an_error(api) -> None:  # type: ignore[no-untyped-def]
    add_email(api.engine, "A-1")
    status = get(api).json()["status"]
    assert (
        status["sendingAvailable"] is False and "servidor de correo" in status["unavailableReason"]
    )
    assert get(api).json()["totals"]["error"] == 0


@pytest.mark.parametrize(
    ("change", "word"),
    [
        ({"smtp_from": None}, "remitente"),
        ({"test_recipient_email": None}, "destinatario"),
        ({"app_env": "production"}, "producción"),
    ],
)
def test_each_cause_of_unavailability_is_reported(api, change: dict[str, Any], word: str) -> None:  # type: ignore[no-untyped-def]
    make_sendable(api)
    settings = api.app.state.settings
    assert get(api).json()["status"]["sendingAvailable"] is True
    for key, value in change.items():
        setattr(settings, key, value)
    status = get(api).json()["status"]
    assert status["sendingAvailable"] is False and word in status["unavailableReason"]


def test_the_response_of_pause_and_resume_also_carries_the_availability(api) -> None:  # type: ignore[no-untyped-def]
    body = post(api, "resume").json()
    assert body["sendingAvailable"] is False and body["unavailableReason"]
