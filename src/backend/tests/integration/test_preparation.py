"""The worker prepares an uploaded file into staging (RF-03, E-01, E-02, E-05, BE-09)."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.adapters.db.preparation import SqlPreparationRepository
from tests.integration.batch_helpers import (
    ADMIN,
    ROW,
    SAMPLES,
    no_definitive_records,
    seed_incident,
    service,
    staged,
    state,
    upload,
)
from tests.integration.test_api import principal_headers  # noqa: F401
from tests.xlsx_builder import HEADERS, build, simple

pytestmark = pytest.mark.integration


# --- E-01 ---------------------------------------------------------------------------------------------------


def test_a_valid_file_with_only_the_three_mandatory_headers_goes_to_review(client) -> None:  # type: ignore[no-untyped-def]
    content = simple([ROW])
    batch_id = upload(client, content)
    assert service(client).process_pending() == 1
    batch = state(client, batch_id)
    assert batch["state"] == "in_review"
    assert batch["reviewedVersion"] == hashlib.sha256(content).hexdigest()
    assert staged(client, batch_id) == [(2, "new", "")]
    no_definitive_records(client)


def test_the_sample_file_is_classified_row_by_row(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, (SAMPLES / "incidencias.xlsx").read_bytes())
    service(client).process_pending()
    rows = staged(client, batch_id)
    counts = {
        c: sum(1 for _, k, _ in rows if k == c) for c in ("new", "duplicate", "conflict", "error")
    }
    assert len(rows) == 18
    assert counts == {"new": 8, "duplicate": 2, "conflict": 2, "error": 6}
    no_definitive_records(client)


def test_nothing_is_prepared_before_the_worker_runs(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    assert state(client, batch_id)["state"] == "processing"
    assert staged(client, batch_id) == []
    no_definitive_records(client)


# --- E-02: whole-file rejections ---------------------------------------------------------------------------


def test_a_missing_mandatory_header_rejects_the_file_with_its_name(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([], headers=[("s", "Proveedor"), ("s", "Fecha y hora")]))
    service(client).process_pending()
    batch = state(client, batch_id)
    assert batch["state"] == "rejected"
    assert batch["rejection"] == {"reason": "missing_required_header", "detail": "Order ID"}
    assert staged(client, batch_id) == []


def test_several_worksheets_reject_the_file(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, build([[HEADERS], [HEADERS]]))
    service(client).process_pending()
    assert state(client, batch_id)["rejection"]["reason"] == "multiple_worksheets"


@pytest.mark.parametrize(
    "content", [b"not a spreadsheet", bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 100]
)
def test_corrupt_and_protected_files_are_rejected(client, content: bytes) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, content)
    service(client).process_pending()
    assert state(client, batch_id)["rejection"]["reason"] == "corrupt_or_protected_file"


def test_a_file_over_10_mb_is_rejected_entirely(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, b"0" * (10 * 1024 * 1024 + 1))
    service(client).process_pending()
    batch = state(client, batch_id)
    assert batch["state"] == "rejected"
    assert "10 MB" in batch["rejection"]["detail"]


def test_a_rejected_batch_does_not_block_the_next_upload(client) -> None:  # type: ignore[no-untyped-def]
    upload(client, b"nope")
    service(client).process_pending()
    again = client.post(
        "/api/batches",
        json={"fileName": "b.xlsx", "sizeBytes": 1},
        headers=principal_headers(ADMIN),
    )
    assert again.status_code == 201


# --- E-05 --------------------------------------------------------------------------------------------------


def test_an_absent_branch_is_valid_and_an_unknown_one_is_an_error(client) -> None:  # type: ignore[no-untyped-def]
    headers = [*HEADERS, ("s", "Sucursal")]
    rows = [[*ROW, None], [("s", "uber eats"), ("s", "UE-2"), ("s", "2026-11-02"), ("s", "playa")]]
    batch_id = upload(client, simple(rows, headers))
    service(client).process_pending()
    result = staged(client, batch_id)
    assert [(n, c) for n, c, _ in result] == [(2, "new"), (3, "error")]
    assert "playa" in result[1][2]


# --- against existing incidents --------------------------------------------------------------------------------


def test_a_row_equal_to_an_existing_incident_is_a_duplicate(client) -> None:  # type: ignore[no-untyped-def]
    seed_incident(client)
    batch_id = upload(client, simple([ROW]))
    service(client).process_pending()
    assert [(n, c) for n, c, _ in staged(client, batch_id)] == [(2, "duplicate")]
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 1


def test_a_row_that_differs_from_an_existing_incident_is_a_conflict_pointing_at_it(client) -> None:  # type: ignore[no-untyped-def]
    seed_incident(client, claim="99")
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    batch_id = upload(client, simple([[*ROW, ("n", "12.50")]], headers))
    service(client).process_pending()
    assert [(n, c) for n, c, _ in staged(client, batch_id)] == [(2, "conflict")]
    with client.engine.connect() as conn:
        linked = conn.execute(text("SELECT existing_incident_id FROM batch_row")).scalar()
        stored = conn.execute(text("SELECT claim_amount::text FROM batch_row")).scalar()
    assert linked is not None
    assert stored == "12.50"  # the digits of the file, not a rounded value


def test_the_staged_values_keep_precision_and_absence(client) -> None:  # type: ignore[no-untyped-def]
    headers = [*HEADERS, ("s", "Importe a reclamar"), ("s", "Total")]
    batch_id = upload(client, simple([[*ROW, ("n", "12.345"), None]], headers))
    service(client).process_pending()
    with client.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT claim_amount::text, total, incident_date::text, incident_time::text, "
                "branch FROM batch_row WHERE batch_id = :b"
            ),
            {"b": batch_id},
        ).one()
    assert row == ("12.345", None, "2026-11-02", "12:15:00", None)


# --- the identical-file notice (RN-11) ----------------------------------------------------------------------------


def test_a_file_identical_to_a_confirmed_one_is_flagged_but_still_classified(client) -> None:  # type: ignore[no-untyped-def]
    content = simple([ROW])
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO batch (id, owner, state, file_name, size_bytes, blob_name, sha256, "
                "confirmed_at) VALUES ('11111111-1111-1111-1111-111111111111', 'x', 'confirmed', "
                "'old.xlsx', 1, 'batches/old.xlsx', :h, '2026-11-20T12:00:00Z')"
            ),
            {"h": hashlib.sha256(content).hexdigest()},
        )
    batch_id = upload(client, content)
    service(client).process_pending()
    batch = state(client, batch_id)
    assert batch["state"] == "in_review"
    assert batch["identicalFile"] == {
        "confirmedBatchId": "11111111-1111-1111-1111-111111111111",
        "confirmedAt": "2026-11-20T12:00:00Z",
    }
    assert [(n, c) for n, c, _ in staged(client, batch_id)] == [(2, "new")]


# --- BE-09: restarts --------------------------------------------------------------------------------------------------


def test_a_batch_being_processed_is_not_taken_by_another_worker_until_its_lease_ends(
    client,
) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    repository = SqlPreparationRepository(client.engine)
    now = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
    claimed = repository.claim_next(now, timedelta(minutes=5))
    assert claimed is not None and claimed.id == batch_id
    assert repository.claim_next(now + timedelta(minutes=1), timedelta(minutes=5)) is None
    again = repository.claim_next(now + timedelta(minutes=6), timedelta(minutes=5))
    assert again is not None and again.id == batch_id


def test_after_a_restart_the_work_continues_and_creates_no_incident(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    repository = SqlPreparationRepository(client.engine)
    died_at = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
    assert (
        repository.claim_next(died_at, timedelta(minutes=5)) is not None
    )  # ...and the worker dies
    assert state(client, batch_id)["state"] == "processing"

    later = died_at + timedelta(minutes=10)
    assert service(client, later).process_pending() == 1
    assert state(client, batch_id)["state"] == "in_review"
    assert staged(client, batch_id) == [(2, "new", "")]
    no_definitive_records(client)


def test_preparing_twice_leaves_one_copy_of_the_staging(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    repository = SqlPreparationRepository(client.engine)
    service(client).process_pending()
    # Force the batch back to processing, as a takeover after a crash that lost the result would.
    with client.engine.begin() as conn:
        conn.execute(text("UPDATE batch SET state = 'processing', lease_until = NULL"))
    assert repository is not None
    service(client).process_pending()
    assert staged(client, batch_id) == [(2, "new", "")]


def test_a_batch_discarded_while_processing_is_left_alone(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    repository = SqlPreparationRepository(client.engine)
    claimed = repository.claim_next(datetime.now(UTC), timedelta(minutes=5))
    assert claimed is not None
    with client.engine.begin() as conn:
        conn.execute(text("UPDATE batch SET state = 'discarded'"))
    assert not repository.save_rejected(batch_id, "corrupt_or_protected_file", "x", None)
    assert staged(client, batch_id) == []


# --- audit -------------------------------------------------------------------------------------------------------------


def test_preparation_is_audited_with_the_system_as_actor(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    service(client).process_pending()
    with client.engine.connect() as conn:
        row = conn.execute(
            text("SELECT actor, outcome FROM audit_log WHERE operation = 'batch.prepare'")
        ).one()
        assert row == ("system:worker", "success")
        assert (
            conn.execute(
                text("SELECT object_id FROM audit_log WHERE operation = 'batch.prepare'")
            ).scalar()
            == batch_id
        )
