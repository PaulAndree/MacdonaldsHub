"""Physical cleanup and its coordination with confirmation (RF-17, ADR-14): BE-05, E-11."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import text

from app.adapters.db.cleanup import SqlCleanupRepository
from app.adapters.db.original_copy import SqlOriginalCopyRepository
from app.services.cleanup import CleanupService
from app.services.original_copy import OriginalCopyService
from tests.integration.batch_helpers import ADMIN, ROW, service, upload
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import simple

pytestmark = pytest.mark.integration


def cleaner(client: Any, storage: Any = None) -> CleanupService:
    return CleanupService(
        SqlCleanupRepository(client.engine), storage or client.app.state.container.storage()
    )


def copier(client: Any) -> OriginalCopyService:
    return OriginalCopyService(
        SqlOriginalCopyRepository(client.engine), client.app.state.container.storage()
    )


def prepared(client: Any, who: str = ADMIN) -> tuple[str, str]:
    batch_id = upload(client, simple([ROW]), who)
    service(client).process_pending()
    version = client.get(f"/api/batches/{batch_id}", headers=principal_headers(who)).json()[
        "reviewedVersion"
    ]
    return batch_id, version


def blob_name(client: Any, batch_id: str) -> str:
    with client.engine.connect() as conn:
        return conn.execute(  # type: ignore[no-any-return]
            text("SELECT blob_name FROM batch WHERE id = :b"), {"b": batch_id}
        ).scalar()


def exists(client: Any, container: str, name: str) -> bool:
    return client.app.state.container.storage().get_blob_info(container, name) is not None


def cleanup_state(client: Any, batch_id: str) -> tuple[str, str | None]:
    with client.engine.connect() as conn:
        return tuple(  # type: ignore[return-value]
            conn.execute(
                text("SELECT cleanup, cleanup_error FROM batch WHERE id = :b"), {"b": batch_id}
            ).one()
        )


def discard(client: Any, batch_id: str, who: str = ADMIN) -> Any:
    return client.post(f"/api/batches/{batch_id}/discard", headers=principal_headers(who))


def confirm(client: Any, batch_id: str, version: str, who: str = ADMIN) -> Any:
    return client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(who),
    )


# --- E-11: the file and the staging disappear -----------------------------------------------------------------------


def test_a_discarded_batch_loses_its_file_and_the_cleanup_is_recorded(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    name = blob_name(client, batch_id)
    discard(client, batch_id)
    assert exists(client, "uploads", name)  # still there until the worker runs
    assert cleaner(client).process_pending() == 1
    assert not exists(client, "uploads", name)
    assert cleanup_state(client, batch_id) == ("done", None)
    with client.engine.connect() as conn:
        entry = conn.execute(
            text("SELECT actor, outcome FROM audit_log WHERE operation = 'batch.cleanup'")
        ).one()
        assert entry == ("system:worker", "success")
        assert conn.execute(text("SELECT count(*) FROM batch_row")).scalar() == 0


def test_a_rejected_batch_loses_its_file_too(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, b"not a spreadsheet")
    service(client).process_pending()
    name = blob_name(client, batch_id)
    assert cleaner(client).process_pending() == 1
    assert not exists(client, "uploads", name)


def test_a_second_run_has_nothing_left_to_clean(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    discard(client, batch_id)
    assert cleaner(client).process_pending() == 1
    assert cleaner(client).process_pending() == 0


def test_a_file_already_gone_counts_as_removed(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    client.app.state.container.storage().delete_blob("uploads", blob_name(client, batch_id))
    discard(client, batch_id)
    cleaner(client).process_pending()
    assert cleanup_state(client, batch_id) == ("done", None)


# --- a failed removal is recorded and completed later ----------------------------------------------------------------


def test_a_failed_removal_is_recorded_not_claimed_and_completed_later(client, caplog) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    name = blob_name(client, batch_id)
    discard(client, batch_id)
    real = client.app.state.container.storage()

    class Failing:
        def __getattr__(self, attr: str) -> Any:
            return getattr(real, attr)

        def delete_blob(self, container: str, blob: str) -> None:
            raise OSError("the store is not reachable")

    with caplog.at_level(logging.WARNING):
        assert cleaner(client, Failing()).process_pending() == 0
    status, error = cleanup_state(client, batch_id)
    assert status == "failed" and "not reachable" in (error or "")
    assert exists(client, "uploads", name)  # nothing is said to be removed that is still stored
    with client.engine.connect() as conn:
        outcome = conn.execute(
            text("SELECT outcome FROM audit_log WHERE operation = 'batch.cleanup'")
        ).scalar()
    assert outcome == "failure"
    assert any("cleanup.retry" in r.getMessage() for r in caplog.records)

    assert cleaner(client).process_pending() == 1  # the next run completes it
    assert cleanup_state(client, batch_id) == ("done", None)
    assert not exists(client, "uploads", name)


# --- confirmed batches are protected -------------------------------------------------------------------------------------------


def test_the_file_of_a_confirmed_batch_is_kept_until_its_original_is_verified(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version = prepared(client)
    name = blob_name(client, batch_id)
    assert confirm(client, batch_id, version).status_code == 200
    assert cleaner(client).process_pending() == 0  # the copy is not verified yet
    assert exists(client, "uploads", name)

    assert copier(client).process_pending() == 1  # now the original is stored and verified
    assert cleaner(client).process_pending() == 1
    assert not exists(client, "uploads", name)  # the temporary file may go...
    assert exists(client, "confirmed", f"batches/{batch_id}.xlsx")  # ...the original never does


def test_cleanup_never_touches_the_confirmed_store_nor_a_batch_under_review(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _ = prepared(client)
    name = blob_name(client, batch_id)
    assert cleaner(client).process_pending() == 0
    assert exists(client, "uploads", name)


def test_the_confirmed_store_refuses_deletion_even_if_asked(client) -> None:  # type: ignore[no-untyped-def]
    from app.services.ports import ImmutableContainerError

    with pytest.raises(ImmutableContainerError):
        client.app.state.container.storage().delete_blob("confirmed", "batches/x.xlsx")


# --- BE-05: concurrent confirmation, discard and cleanup -----------------------------------------------------------------------------


def test_confirmation_and_discard_at_the_same_time_never_both_win(client) -> None:  # type: ignore[no-untyped-def]
    users = [f"u{i}@example.test" for i in range(12)]
    with client.engine.begin() as conn:
        for email in users:
            conn.execute(
                text(
                    "INSERT INTO allowlist_entry (id, identifier, email, role) "
                    "VALUES (gen_random_uuid(), :e, :e, 'administrator')"
                ),
                {"e": email},
            )
    outcomes: list[str] = []
    for index, who in enumerate(users):
        content = simple([[("s", "uber eats"), ("s", f"UE-{index}"), ("s", "2026-11-02")]])
        batch_id = upload(client, content, who)
        service(client).process_pending()
        version = client.get(f"/api/batches/{batch_id}", headers=principal_headers(who)).json()[
            "reviewedVersion"
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            confirming = pool.submit(confirm, client, batch_id, version, who)
            discarding = pool.submit(discard, client, batch_id, who)
            cleaning = pool.submit(cleaner(client).process_pending)
            c, d = confirming.result(), discarding.result()
            cleaning.result()
        with client.engine.connect() as conn:
            final = conn.execute(
                text("SELECT state FROM batch WHERE id = :b"), {"b": batch_id}
            ).scalar()
            incidents = conn.execute(
                text("SELECT count(*) FROM incident WHERE batch_id = :b"), {"b": batch_id}
            ).scalar()
        if final == "discarded":
            assert (c.status_code, d.status_code) == (409, 200) and incidents == 0
        else:
            assert final in ("confirmed", "completed")
            assert (c.status_code, d.status_code) == (200, 409) and incidents == 1
            copier(client).process_pending()
            cleaner(client).process_pending()
            assert exists(client, "confirmed", f"batches/{batch_id}.xlsx")  # never lost
        outcomes.append(final)
    assert set(outcomes) <= {"discarded", "confirmed", "completed"}
