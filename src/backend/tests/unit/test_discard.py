"""Explicit discard (RF-17): cancel and Cerrar sesión, without expiry (E-11, BE-04, BE-15, BE-16)."""

import pytest

from app.services.batches import (
    BatchAlreadyConfirmed,
    BatchNotFound,
    BatchService,
    UnconfirmedBatchExists,
)
from tests.fakes import NOW, FakeStorage, FakeUow


def make() -> tuple[BatchService, FakeUow, FakeStorage]:
    uow, storage = FakeUow(), FakeStorage()
    counter = iter(range(1, 100))
    service = BatchService(uow, storage, clock=lambda: NOW, new_id=lambda: f"b-{next(counter)}")
    return service, uow, storage


@pytest.mark.parametrize("state", ["uploaded", "processing", "in_review", "rejected"])
def test_a_batch_can_be_discarded_before_it_is_confirmed(state: str) -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    uow.batches.set_state(batch.id, state)
    discarded = service.discard("ana", batch.id)
    assert discarded.state == "discarded"
    assert uow.batches.cleanup[batch.id] == "pending"  # file and staging are removed afterwards


def test_a_stuck_processing_batch_does_not_block_the_user() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    uow.batches.set_state(batch.id, "processing")
    service.discard("ana", batch.id)
    service.create("ana", "b.xlsx", 1)  # allowed again


@pytest.mark.parametrize("state", ["confirmed", "completed"])
def test_a_confirmed_batch_cannot_be_discarded(state: str) -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    uow.batches.set_state(batch.id, state)
    with pytest.raises(BatchAlreadyConfirmed):
        service.discard("ana", batch.id)
    assert uow.batches.rows[batch.id].state == state


def test_discarding_twice_is_harmless_and_audited_once() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    service.discard("ana", batch.id)
    assert service.discard("ana", batch.id).state == "discarded"
    assert [e.operation for e in uow.log.entries].count("batch.discard") == 1


def test_a_batch_of_another_user_is_not_found() -> None:
    service, _, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    with pytest.raises(BatchNotFound):
        service.discard("luis", batch.id)


def test_the_audit_of_a_discard_holds_no_content() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "secret-name.xlsx", 1)
    service.discard("ana", batch.id)
    entry = next(e for e in uow.log.entries if e.operation == "batch.discard")
    assert entry.object_id == batch.id and entry.actor == "ana"
    assert entry.details == {"previous": "uploaded"}
    assert "secret-name" not in repr(entry)


def test_cerrar_sesion_discards_every_unconfirmed_batch_of_the_user_and_nobody_elses() -> None:
    service, uow, _ = make()
    mine, _ = service.create("ana", "a.xlsx", 1)
    other, _ = service.create("luis", "b.xlsx", 1)
    assert service.discard_unconfirmed("ana") == [mine.id]
    assert uow.batches.rows[mine.id].state == "discarded"
    assert uow.batches.rows[other.id].state == "uploaded"


def test_cerrar_sesion_with_nothing_to_discard_changes_nothing() -> None:
    service, uow, _ = make()
    assert service.discard_unconfirmed("ana") == []
    assert uow.log.entries == []


def test_cerrar_sesion_leaves_confirmed_batches_alone() -> None:
    service, uow, _ = make()
    batch, _ = service.create("ana", "a.xlsx", 1)
    uow.batches.set_state(batch.id, "confirmed")
    assert service.discard_unconfirmed("ana") == []
    assert uow.batches.rows[batch.id].state == "confirmed"


def test_the_pending_batch_is_the_unconfirmed_one_and_there_is_none_after_discarding() -> None:
    service, _, _ = make()
    assert service.pending("ana") is None
    batch, _ = service.create("ana", "a.xlsx", 1)
    pending = service.pending("ana")
    assert pending is not None and pending.id == batch.id
    service.discard("ana", batch.id)
    assert service.pending("ana") is None


def test_a_second_batch_names_the_pending_one() -> None:
    service, _, _ = make()
    first, _ = service.create("ana", "a.xlsx", 1)
    with pytest.raises(UnconfirmedBatchExists) as caught:
        service.create("ana", "b.xlsx", 1)
    assert caught.value.batch_id == first.id
