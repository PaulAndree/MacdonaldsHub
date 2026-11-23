"""Registering a batch and recording its upload (RF-01, ADR-14, E-01, BE-16 without concurrency)."""

import pytest

from app.services.batches import (
    BatchNotFound,
    BatchService,
    UnconfirmedBatchExists,
    UploadNotFound,
)
from tests.fakes import NOW, FakeStorage, FakeUow


def make() -> tuple[BatchService, FakeUow, FakeStorage]:
    uow, storage = FakeUow(), FakeStorage()
    counter = iter(range(1, 100))
    service = BatchService(uow, storage, clock=lambda: NOW, new_id=lambda: f"batch-{next(counter)}")
    return service, uow, storage


def test_a_new_batch_is_uploaded_and_gets_a_create_only_grant_for_its_own_blob() -> None:
    service, uow, storage = make()
    batch, grant = service.create("ana", "incidencias.xlsx", 48213)
    assert (batch.state, batch.owner, batch.file_name) == ("uploaded", "ana", "incidencias.xlsx")
    assert batch.created_at == NOW
    assert grant.method == "PUT" and grant.headers["If-None-Match"] == "*"
    assert storage.granted == [batch.blob_name]
    assert batch.blob_name != "incidencias.xlsx"  # the browser never chooses the blob name


def test_each_batch_gets_its_own_blob() -> None:
    service, uow, storage = make()
    first, _ = service.create("ana", "a.xlsx", 1)
    uow.batches.set_state(first.id, "rejected")
    second, _ = service.create("ana", "a.xlsx", 1)
    assert first.blob_name != second.blob_name


def test_creating_a_batch_is_audited() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    (entry,) = uow.log.entries
    assert (entry.actor, entry.operation, entry.object_type, entry.object_id) == (
        "ana",
        "batch.create",
        "batch",
        batch.id,
    )
    assert entry.outcome == "success"


def test_a_user_with_an_unconfirmed_batch_gets_a_refusal_naming_it() -> None:
    service, uow, storage = make()
    first, _ = service.create("ana", "a.xlsx", 10)
    with pytest.raises(UnconfirmedBatchExists) as caught:
        service.create("ana", "b.xlsx", 10)
    assert caught.value.batch_id == first.id
    assert len(storage.granted) == 1  # no grant is issued for the refused request
    assert len(uow.batches.rows) == 1


def test_another_user_is_not_blocked() -> None:
    service, _, _ = make()
    service.create("ana", "a.xlsx", 10)
    service.create("luis", "a.xlsx", 10)


def test_completing_the_upload_requests_processing() -> None:
    service, uow, storage = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    storage.blobs[("uploads", batch.blob_name)] = 10
    done = service.complete_upload("ana", batch.id)
    assert done.state == "processing"
    assert [e.operation for e in uow.log.entries] == ["batch.create", "batch.upload_complete"]


def test_completing_twice_is_harmless() -> None:
    service, uow, storage = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    storage.blobs[("uploads", batch.blob_name)] = 10
    service.complete_upload("ana", batch.id)
    again = service.complete_upload("ana", batch.id)
    assert again.state == "processing"
    assert [e.operation for e in uow.log.entries].count("batch.upload_complete") == 1


def test_a_file_that_never_arrived_is_refused_and_the_batch_does_not_move() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    with pytest.raises(UploadNotFound):
        service.complete_upload("ana", batch.id)
    assert uow.batches.rows[batch.id].state == "uploaded"


def test_a_batch_of_another_user_looks_like_it_does_not_exist() -> None:
    service, _, storage = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    storage.blobs[("uploads", batch.blob_name)] = 10
    with pytest.raises(BatchNotFound):
        service.complete_upload("luis", batch.id)
    with pytest.raises(BatchNotFound):
        service.get("luis", batch.id)


def test_an_unknown_batch_is_not_found() -> None:
    service, _, _ = make()
    with pytest.raises(BatchNotFound):
        service.get("ana", "nope")


def test_a_discarded_batch_cannot_be_completed() -> None:
    service, uow, storage = make()
    batch, _ = service.create("ana", "a.xlsx", 10)
    storage.blobs[("uploads", batch.blob_name)] = 10
    uow.batches.set_state(batch.id, "discarded")
    with pytest.raises(BatchNotFound):
        service.complete_upload("ana", batch.id)
