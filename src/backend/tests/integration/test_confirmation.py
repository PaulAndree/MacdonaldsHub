"""Atomic, idempotent confirmation with a real PostgreSQL (RF-07..RF-10): E-06..E-08, BE-02, BE-03."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import text

from tests.integration.batch_helpers import ADMIN, ROW, SAMPLES, seed_incident, service, upload
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import HEADERS, simple

pytestmark = pytest.mark.integration


def prepared(client: Any, content: bytes) -> tuple[str, str]:
    batch_id = upload(client, content)
    service(client).process_pending()
    batch = client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()
    assert batch["state"] == "in_review"
    return batch_id, batch["reviewedVersion"]


def confirm(client: Any, batch_id: str, version: str, who: str = ADMIN) -> Any:
    return client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(who),
    )


def counts(client: Any) -> dict[str, int]:
    with client.engine.connect() as conn:
        return {
            t: conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()  # noqa: S608
            for t in ("incident", "outbox", "incident_history", "batch_row")
        }


def eighty() -> bytes:
    rows = [[("s", "uber eats"), ("s", f"UE-{i}"), ("s", "2026-11-02")] for i in range(20)]
    rows += [[("s", "just eat"), ("s", f"JE-{i}"), ("s", "2026-11-02")] for i in range(40)]
    rows += [[("s", "glovo"), ("s", f"GL-{i}"), ("s", "2026-11-02")] for i in range(20)]
    return simple(rows)


# --- the summary shown before confirming ------------------------------------------------------------------------


def test_the_summary_says_what_confirming_will_do(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, (SAMPLES / "incidencias.xlsx").read_bytes())
    summary = client.get(
        f"/api/batches/{batch_id}/confirmation-summary", headers=principal_headers(ADMIN)
    ).json()
    assert summary["reviewedVersion"] == version
    assert (summary["incidentsToCreate"], summary["emailsToGenerate"]) == (8, 7)
    assert (summary["withoutEmail"], summary["excluded"]) == (1, 10)
    assert summary["recipient"] == {"kind": "test", "label": "Destinatario de prueba"}
    assert summary["template"]["isFinal"] is False
    assert summary["template"]["pendingDecision"] == "P-03"
    assert "{orderId}" in summary["template"]["body"]


# --- E-06 ----------------------------------------------------------------------------------------------------------


def test_80_new_rows_with_20_glovo_create_80_incidents_and_60_pending_emails(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, eighty())
    assert counts(client)["incident"] == 0  # nothing definitive before confirming
    response = confirm(client, batch_id, version)
    assert response.status_code == 200
    body = response.json()
    assert (body["createdIncidents"], body["pendingEmails"], body["withoutEmail"]) == (80, 60, 20)
    assert body["alreadyConfirmed"] is False
    done = counts(client)
    assert (done["incident"], done["outbox"]) == (80, 60)
    assert done["incident_history"] == 80
    assert done["batch_row"] == 0  # the staging is cleaned
    with client.engine.connect() as conn:
        states = dict(conn.execute(text("SELECT state, count(*) FROM outbox GROUP BY state")).all())
        assert states == {"pending": 60}  # nothing was sent, nothing started
        started = conn.execute(text("SELECT count(*) FROM outbox WHERE started_at IS NOT NULL"))
        assert started.scalar() == 0
        kinds = dict(
            conn.execute(text("SELECT state, count(*) FROM incident GROUP BY state")).all()
        )
        assert kinds == {"pending_send": 60, "imported_no_email": 20}
        batch = conn.execute(
            text("SELECT state, confirmed_by, original_copy FROM batch WHERE id = :b"),
            {"b": batch_id},
        ).one()
        assert batch == ("confirmed", ADMIN, "pending")


def test_the_outbox_keeps_the_authorized_recipient_and_text(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    confirm(client, batch_id, version)
    with client.engine.connect() as conn:
        row = conn.execute(
            text("SELECT recipient, template_version, subject, body, state FROM outbox")
        ).one()
    assert row[0] == "test-recipient@example.test"
    assert row[1] == "example-1" and "{orderId}" in row[3] and row[4] == "pending"


def test_incident_values_keep_precision_and_absence(client) -> None:  # type: ignore[no-untyped-def]
    headers = [*HEADERS, ("s", "Importe a reclamar"), ("s", "Total")]
    batch_id, version = prepared(client, simple([[*ROW, ("n", "12.345"), None]], headers))
    confirm(client, batch_id, version)
    with client.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT claim_amount::text, total, incident_date::text, incident_time::text "
                "FROM incident"
            )
        ).one()
    assert row == ("12.345", None, "2026-11-02", "12:15:00")


def test_a_batch_with_only_glovo_is_completed_at_once(client) -> None:  # type: ignore[no-untyped-def]
    rows = [[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02")]]
    batch_id, version = prepared(client, simple(rows))
    # Glovo needs no recipient, so it confirms even without one configured.
    client.app.state.settings.test_recipient_email = None
    body = confirm(client, batch_id, version).json()
    assert (body["createdIncidents"], body["pendingEmails"]) == (1, 0)
    assert (
        client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()["state"]
        == "completed"
    )


def test_the_confirmation_is_audited_with_the_reviewed_hash(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    confirm(client, batch_id, version)
    with client.engine.connect() as conn:
        row = conn.execute(
            text("SELECT actor, outcome, details FROM audit_log WHERE operation = 'batch.confirm'")
        ).one()
    assert row[0] == ADMIN and row[1] == "success"
    assert row[2]["sha256"] == version and row[2]["createdIncidents"] == 1


# --- E-07, BE-11: idempotency --------------------------------------------------------------------------------------


def test_repeating_the_confirmation_returns_the_stored_result_and_adds_nothing(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, eighty())
    first = confirm(client, batch_id, version).json()
    before = counts(client)
    second = confirm(client, batch_id, version).json()
    assert second["alreadyConfirmed"] is True
    assert {k: v for k, v in second.items() if k != "alreadyConfirmed"} == {
        k: v for k, v in first.items() if k != "alreadyConfirmed"
    }
    assert counts(client) == before
    with client.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE operation = 'batch.confirm'")
            ).scalar()
            == 1
        )


# --- BE-03: simultaneous confirmations -----------------------------------------------------------------------------------


def test_two_simultaneous_confirmations_create_the_records_once(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, eighty())
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: confirm(client, batch_id, version), range(4)))
    assert [r.status_code for r in responses] == [200, 200, 200, 200]
    assert sorted(r.json()["alreadyConfirmed"] for r in responses) == [False, True, True, True]
    done = counts(client)
    assert (done["incident"], done["outbox"]) == (80, 60)
    with client.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE operation = 'batch.confirm'")
            ).scalar()
            == 1
        )


# --- E-08: a failure leaves nothing -------------------------------------------------------------------------------------


def test_a_failure_midway_leaves_no_incident_outbox_or_confirmation(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, eighty())
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION fail_outbox() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN IF (SELECT count(*) FROM outbox) >= 30 THEN "
                "RAISE EXCEPTION 'disk full'; END IF; RETURN NEW; END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox "
                "FOR EACH ROW EXECUTE FUNCTION fail_outbox()"
            )
        )
    with pytest.raises(Exception, match="disk full"):  # the server error reaches the test client
        client.post(
            f"/api/batches/{batch_id}/confirm",
            json={"reviewedVersion": version},
            headers=principal_headers(ADMIN),
        )
    with client.engine.connect() as conn:
        assert counts(client)["incident"] == 0 and counts(client)["outbox"] == 0
        assert counts(client)["incident_history"] == 0
        assert counts(client)["batch_row"] == 80  # the review is intact
        assert conn.execute(text("SELECT state FROM batch")).scalar() == "in_review"
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE operation = 'batch.confirm'")
            ).scalar()
            == 0
        )
    # The user can try again once the cause is gone, with the same reviewed batch.
    with client.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER fail_outbox ON outbox"))
    assert confirm(client, batch_id, version).json()["createdIncidents"] == 80


# --- BE-02: matches that appear during the review -------------------------------------------------------------------------


def test_a_key_created_meanwhile_is_excluded_and_the_rest_is_imported(client) -> None:  # type: ignore[no-untyped-def]
    rows = [
        [("s", "uber eats"), ("s", "UE-1"), ("s", "2026-11-02 12:15")],
        [("s", "uber eats"), ("s", "UE-2"), ("s", "2026-11-02 12:15")],
    ]
    batch_id, version = prepared(client, simple(rows))
    seed_incident(client, "UE-1")  # another batch confirms UE-1 while this one is under review
    body = confirm(client, batch_id, version).json()
    assert body["createdIncidents"] == 1 and body["pendingEmails"] == 1
    assert body["excludedAtConfirmation"] == [
        {
            "rowNumber": 2,
            "class": "duplicate",
            "reason": "Otro lote confirmó esta incidencia mientras se revisaba.",
        }
    ]
    assert counts(client)["outbox"] == 1


def test_a_key_created_meanwhile_with_other_data_is_reported_as_a_conflict(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    seed_incident(client, "UE-1", claim="99")
    body = confirm(client, batch_id, version).json()
    assert body["excludedAtConfirmation"][0]["class"] == "conflict"
    assert body["createdIncidents"] == 0 and counts(client)["outbox"] == 0


# --- who and what may be confirmed ----------------------------------------------------------------------------------------


def test_a_discarded_batch_is_not_confirmable(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    with client.engine.begin() as conn:
        conn.execute(text("UPDATE batch SET state = 'discarded'"))
    response = confirm(client, batch_id, version)
    assert response.status_code == 409 and response.json()["code"] == "batch_discarded"
    assert counts(client)["incident"] == 0


def test_a_different_file_version_is_refused(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client, simple([ROW]))
    response = confirm(client, batch_id, "0" * 64)
    assert response.status_code == 422 and response.json()["code"] == "reviewed_version_mismatch"
    assert counts(client)["incident"] == 0


def test_a_batch_still_processing_cannot_be_confirmed(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    response = confirm(client, batch_id, "0" * 64)
    assert response.status_code == 409 and response.json()["code"] == "batch_not_reviewable"


def test_emails_without_an_authorized_recipient_are_refused(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    client.app.state.settings.test_recipient_email = None
    response = confirm(client, batch_id, version)
    assert response.status_code == 409 and response.json()["code"] == "recipient_not_configured"
    assert counts(client)["incident"] == 0


def test_another_user_or_an_unknown_batch_is_not_found(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, simple([ROW]))
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), 'o@example.test', 'o@example.test', 'administrator'), "
                "(gen_random_uuid(), 'm@example.test', 'm@example.test', 'global_manager')"
            )
        )
    assert confirm(client, batch_id, version, who="o@example.test").status_code == 404
    assert confirm(client, "00000000-0000-0000-0000-000000000000", version).status_code == 404
    assert confirm(client, batch_id, version, who="m@example.test").status_code == 403
    assert counts(client)["incident"] == 0


def test_the_request_needs_a_valid_reviewed_version(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client, simple([ROW]))
    for body in ({}, {"reviewedVersion": "not-a-hash"}):
        response = client.post(
            f"/api/batches/{batch_id}/confirm", json=body, headers=principal_headers(ADMIN)
        )
        assert response.status_code == 422 and response.json()["code"] == "invalid_request"


# --- BE-07 and nothing is sent -----------------------------------------------------------------------------------------


def test_editing_the_recipient_or_template_afterwards_does_not_change_the_outbox(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client, eighty())
    confirm(client, batch_id, version)
    client.app.state.settings.test_recipient_email = "someone-else@example.test"
    with client.engine.connect() as conn:
        recipients = {r[0] for r in conn.execute(text("SELECT recipient FROM outbox"))}
        versions = {r[0] for r in conn.execute(text("SELECT template_version FROM outbox"))}
    assert recipients == {"test-recipient@example.test"} and versions == {"example-1"}
    # A repeated confirmation still answers with the stored result, not a new authorization.
    assert confirm(client, batch_id, version).json()["alreadyConfirmed"] is True


def test_confirming_sends_no_email(client) -> None:  # type: ignore[no-untyped-def]
    import os

    import httpx

    base = os.environ.get("TEST_MAILPIT_URL")
    if not base:
        pytest.skip("TEST_MAILPIT_URL is not set")
    httpx.delete(f"{base}/api/v1/messages")
    batch_id, version = prepared(client, eighty())
    confirm(client, batch_id, version)
    assert httpx.get(f"{base}/api/v1/messages").json()["total"] == 0
    with client.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM outbox WHERE state <> 'pending'")).scalar() == 0
        )
