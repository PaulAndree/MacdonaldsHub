"""The confirmed original is copied to the immutable store after the commit (ADR-14, RF-19)."""

import hashlib
import logging
from typing import Any

import pytest
from sqlalchemy import text

from app.adapters.db.original_copy import SqlOriginalCopyRepository
from app.services.original_copy import OriginalCopyService
from tests.integration.batch_helpers import ADMIN, ROW, service, upload
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import simple

pytestmark = pytest.mark.integration


def confirmed_batch(client: Any) -> tuple[str, str, bytes]:
    content = simple([ROW])
    batch_id = upload(client, content)
    service(client).process_pending()
    version = client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()[
        "reviewedVersion"
    ]
    done = client.post(
        f"/api/batches/{batch_id}/confirm",
        json={"reviewedVersion": version},
        headers=principal_headers(ADMIN),
    )
    assert done.status_code == 200
    return batch_id, version, content


def copier(client: Any, storage: Any = None) -> OriginalCopyService:
    return OriginalCopyService(
        SqlOriginalCopyRepository(client.engine), storage or client.app.state.container.storage()
    )


def status(client: Any, batch_id: str) -> str:
    with client.engine.connect() as conn:
        return conn.execute(  # type: ignore[no-any-return]
            text("SELECT original_copy FROM batch WHERE id = :b"), {"b": batch_id}
        ).scalar()


def test_nothing_is_copied_until_the_worker_runs_and_the_batch_is_already_confirmed(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _, _ = confirmed_batch(client)
    storage = client.app.state.container.storage()
    assert status(client, batch_id) == "pending"
    assert storage.get_blob_info("confirmed", f"batches/{batch_id}.xlsx") is None


def test_the_original_is_copied_verified_and_linked(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version, content = confirmed_batch(client)
    assert copier(client).process_pending() == 1
    storage = client.app.state.container.storage()
    stored = storage.read_blob("confirmed", f"batches/{batch_id}.xlsx")
    assert hashlib.sha256(stored).hexdigest() == version and stored == content
    assert status(client, batch_id) == "verified"
    with client.engine.connect() as conn:
        entry = conn.execute(
            text(
                "SELECT actor, outcome, details FROM audit_log "
                "WHERE operation = 'batch.original_verified'"
            )
        ).one()
    assert entry[0] == "system:worker" and entry[1] == "success"
    assert entry[2] == {"sha256": version, "object": f"confirmed/batches/{batch_id}.xlsx"}


def test_the_temporary_file_is_kept_after_copying(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, _, _ = confirmed_batch(client)
    copier(client).process_pending()
    with client.engine.connect() as conn:
        blob = conn.execute(text("SELECT blob_name FROM batch")).scalar()
    assert client.app.state.container.storage().get_blob_info("uploads", blob) is not None


def test_a_second_run_has_nothing_to_do(client) -> None:  # type: ignore[no-untyped-def]
    confirmed_batch(client)
    assert copier(client).process_pending() == 1
    assert copier(client).process_pending() == 0


def test_a_failed_copy_is_retried_and_the_batch_stays_confirmed(client) -> None:  # type: ignore[no-untyped-def]
    batch_id, version, _ = confirmed_batch(client)
    real = client.app.state.container.storage()

    class Flaky:
        calls = 0

        def __getattr__(self, name: str) -> Any:
            return getattr(real, name)

        def write_new_blob(self, container: str, name: str, data: bytes) -> bool:
            Flaky.calls += 1
            if Flaky.calls == 1:
                raise OSError("the store is not reachable")
            return real.write_new_blob(container, name, data)  # type: ignore[no-any-return]

    flaky = Flaky()
    assert copier(client, flaky).process_pending() == 0  # nothing finished
    assert status(client, batch_id) == "pending"
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT state FROM batch")).scalar() == "confirmed"
    assert copier(client, flaky).process_pending() == 1
    assert status(client, batch_id) == "verified"


def test_a_different_file_already_stored_is_a_discrepancy_that_is_not_replaced(
    client, caplog
) -> None:  # type: ignore[no-untyped-def]
    batch_id, version, _ = confirmed_batch(client)
    storage = client.app.state.container.storage()
    storage.write_new_blob("confirmed", f"batches/{batch_id}.xlsx", b"another file")
    with caplog.at_level(logging.ERROR):
        copier(client).process_pending()
    assert status(client, batch_id) == "discrepancy"
    assert storage.read_blob("confirmed", f"batches/{batch_id}.xlsx") == b"another file"
    with client.engine.connect() as conn:
        entry = conn.execute(
            text("SELECT outcome FROM audit_log WHERE operation = 'batch.original_discrepancy'")
        ).scalar()
        assert entry == "failure"
        assert conn.execute(text("SELECT state FROM batch")).scalar() == "confirmed"
    assert any("original.discrepancy" in r.getMessage() for r in caplog.records)


def test_an_identical_copy_already_stored_is_accepted_as_verified(client) -> None:  # type: ignore[no-untyped-def]
    # A worker that died after writing but before recording finds the same file next time.
    batch_id, _, content = confirmed_batch(client)
    client.app.state.container.storage().write_new_blob(
        "confirmed", f"batches/{batch_id}.xlsx", content
    )
    copier(client).process_pending()
    assert status(client, batch_id) == "verified"
