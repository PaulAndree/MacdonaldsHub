"""Explicit discard, Cerrar sesión, one batch per user and no expiry (RF-17): E-11, BE-04, BE-15, BE-16."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import text

from tests.integration.batch_helpers import ADMIN, ROW, service, upload
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import simple

pytestmark = pytest.mark.integration

BODY = {"fileName": "f.xlsx", "sizeBytes": 10}


def prepared(client: Any, who: str = ADMIN) -> tuple[str, str]:
    batch_id = upload(client, simple([ROW]), who)
    service(client).process_pending()
    version = client.get(f"/api/batches/{batch_id}", headers=principal_headers(who)).json()[
        "reviewedVersion"
    ]
    return batch_id, version


def discard(client: Any, batch_id: str, who: str = ADMIN) -> Any:
    return client.post(f"/api/batches/{batch_id}/discard", headers=principal_headers(who))


def state(client: Any, batch_id: str) -> str:
    with client.engine.connect() as conn:
        return conn.execute(  # type: ignore[no-any-return]
            text("SELECT state FROM batch WHERE id = :b"), {"b": batch_id}
        ).scalar()


def staged_rows(client: Any) -> int:
    with client.engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM batch_row")).scalar()  # type: ignore[no-any-return]


def add_users(client: Any, *emails: str) -> None:
    with client.engine.begin() as conn:
        for email in emails:
            conn.execute(
                text(
                    "INSERT INTO allowlist_entry (id, identifier, email, role) "
                    "VALUES (gen_random_uuid(), :e, :e, 'administrator')"
                ),
                {"e": email},
            )


# --- cancel (E-11) ---------------------------------------------------------------------------------------------------


def test_cancelling_a_batch_under_review_discards_it_and_its_prepared_rows(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    assert staged_rows(client) == 1
    response = discard(client, batch_id)
    assert response.status_code == 200 and response.json()["state"] == "discarded"
    assert staged_rows(client) == 0
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT cleanup FROM batch")).scalar() == "pending"


def test_a_discarded_batch_cannot_be_confirmed(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    discard(client, batch_id)
    response = client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(ADMIN),
    )
    assert response.status_code == 409 and response.json()["code"] == "batch_discarded"
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 0


def test_a_confirmed_batch_cannot_be_cancelled(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(ADMIN),
    )
    response = discard(client, batch_id)
    assert response.status_code == 409 and response.json()["code"] == "batch_already_confirmed"
    assert state(client, batch_id) in ("confirmed", "completed")


def test_another_users_batch_is_not_found_and_stays_as_it_was(client) -> None:  # type: ignore[no-untyped-def]
    add_users(client, "other@example.test")
    batch_id, _ = prepared(client)
    assert discard(client, batch_id, who="other@example.test").status_code == 404
    assert state(client, batch_id) == "in_review"


def test_a_batch_stuck_in_processing_can_be_discarded_and_stops_blocking(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))  # the worker never ran: it stays "processing"
    assert state(client, batch_id) == "processing"
    assert discard(client, batch_id).status_code == 200
    again = client.post("/api/batches", json=BODY, headers=principal_headers(ADMIN))
    assert again.status_code == 201


def test_a_batch_that_was_only_registered_can_be_discarded(client) -> None:  # type: ignore[no-untyped-def]
    created = client.post("/api/batches", json=BODY, headers=principal_headers(ADMIN)).json()
    assert discard(client, created["batch"]["id"]).json()["state"] == "discarded"


def test_a_discard_is_audited_without_rows_or_file_name(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    discard(client, batch_id)
    with client.engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT actor, object_id, details::text FROM audit_log WHERE operation = 'batch.discard'"
            )
        ).all()
    assert rows == [(ADMIN, batch_id, '{"previous": "in_review"}')]


# --- Cerrar sesión ----------------------------------------------------------------------------------------------------------


def test_cerrar_sesion_discards_only_the_users_unconfirmed_batches(client) -> None:  # type: ignore[no-untyped-def]
    add_users(client, "luis@example.test")
    mine, _ = prepared(client)
    theirs, _ = prepared(client, "luis@example.test")
    response = client.post("/api/batches/discard-unconfirmed", headers=principal_headers(ADMIN))
    assert response.status_code == 200
    assert response.json() == {"discarded": 1, "batchIds": [mine]}
    assert state(client, mine) == "discarded" and state(client, theirs) == "in_review"


def test_cerrar_sesion_with_nothing_pending_discards_nothing(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/batches/discard-unconfirmed", headers=principal_headers(ADMIN))
    assert response.json() == {"discarded": 0, "batchIds": []}


def test_cerrar_sesion_is_open_to_any_signed_in_user_even_a_read_only_one(client) -> None:  # type: ignore[no-untyped-def]
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), 'm@example.test', 'm@example.test', 'global_manager')"
            )
        )
    response = client.post(
        "/api/batches/discard-unconfirmed", headers=principal_headers("m@example.test")
    )
    assert response.status_code == 200 and response.json()["discarded"] == 0
    assert client.post("/api/batches/discard-unconfirmed").status_code == 401


def test_cerrar_sesion_leaves_confirmed_batches_alone(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(ADMIN),
    )
    client.post("/api/batches/discard-unconfirmed", headers=principal_headers(ADMIN))
    assert state(client, batch_id) in ("confirmed", "completed")


# --- BE-15: a failed discard changes nothing --------------------------------------------------------------------------------


def test_when_the_discard_fails_the_batch_stays_under_review_unchanged(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "CREATE FUNCTION fail_discard() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN IF NEW.state = 'discarded' THEN RAISE EXCEPTION 'database down'; END IF; "
                "RETURN NEW; END; $$"
            )
        )
        conn.execute(
            text(
                "CREATE TRIGGER fail_discard BEFORE UPDATE ON batch "
                "FOR EACH ROW EXECUTE FUNCTION fail_discard()"
            )
        )
    with pytest.raises(Exception, match="database down"):
        client.post("/api/batches/discard-unconfirmed", headers=principal_headers(ADMIN))
    assert state(client, batch_id) == "in_review"
    assert staged_rows(client) == 1  # the review is intact
    with client.engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_log WHERE operation = 'batch.discard'")
            ).scalar()
            == 0
        )
    # It can still be confirmed, and discarded once the cause is gone.
    with client.engine.begin() as conn:
        conn.execute(text("DROP TRIGGER fail_discard ON batch"))
    assert discard(client, batch_id).status_code == 200


# --- BE-16: one unconfirmed batch per user ------------------------------------------------------------------------------------


def test_simultaneous_requests_never_leave_two_unconfirmed_batches(client) -> None:  # type: ignore[no-untyped-def]
    def register(_: int) -> Any:
        return client.post("/api/batches", json=BODY, headers=principal_headers(ADMIN))

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(register, range(8)))
    codes = sorted(r.status_code for r in responses)
    assert codes == [201] + [409] * 7
    winner = next(r for r in responses if r.status_code == 201).json()["batch"]["id"]
    for refused in (r for r in responses if r.status_code == 409):
        assert refused.json()["details"] == {"batchId": winner}
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM batch")).scalar() == 1


def test_a_rejected_batch_does_not_block_a_new_upload(client) -> None:  # type: ignore[no-untyped-def]
    upload(client, b"not a spreadsheet")
    service(client).process_pending()
    assert (
        client.post("/api/batches", json=BODY, headers=principal_headers(ADMIN)).status_code == 201
    )


# --- the pending batch and the absence of expiry (BE-04) -------------------------------------------------------------------------


def test_the_pending_batch_is_204_when_there_is_none(client) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/batches/pending", headers=principal_headers(ADMIN)).status_code == 204


def test_after_the_browser_closes_the_batch_is_still_under_review_and_confirmable(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    with client.engine.begin() as conn:  # a month goes by
        conn.execute(
            text(
                "UPDATE batch SET created_at = now() - interval '30 days', "
                "updated_at = now() - interval '30 days'"
            )
        )
    service(client).process_pending()  # the worker ticks run; none of them expires anything
    pending = client.get("/api/batches/pending", headers=principal_headers(ADMIN))
    assert pending.status_code == 200
    assert pending.json()["id"] == batch_id and pending.json()["state"] == "in_review"
    assert pending.json()["summary"]["incidentsToCreate"] == 1
    confirmed = client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(ADMIN),
    )
    assert confirmed.status_code == 200 and confirmed.json()["createdIncidents"] == 1


def test_the_user_can_resume_or_cancel_the_pending_batch(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    pending = client.get("/api/batches/pending", headers=principal_headers(ADMIN)).json()
    assert pending["id"] == batch_id
    discard(client, batch_id)
    assert client.get("/api/batches/pending", headers=principal_headers(ADMIN)).status_code == 204
