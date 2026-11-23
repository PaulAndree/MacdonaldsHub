"""Confirmation rules (RF-07..RF-10, RN-03, RN-04): E-06, E-07, BE-02, BE-11, without a database."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.rows import Fields
from app.services.audit import Auditor
from app.services.batches import BatchNotFound, BatchRecord
from app.services.confirmation import (
    AuthorizedEmail,
    BatchNotConfirmable,
    ConfirmationService,
    RecipientNotConfigured,
    ReviewedVersionMismatch,
    StagedForConfirmation,
)
from tests.fake_confirmation import FakeConfirmationStore, source_row
from tests.fakes import NOW, FakeAuditLog

SHA = "a" * 64
EMAIL = AuthorizedEmail("test@example.test", "example-1", "Asunto", "Cuerpo {orderId}")


def batch(state: str = "in_review", owner: str = "ana") -> BatchRecord:
    return BatchRecord(
        id="b-1",
        owner=owner,
        state=state,
        file_name="f.xlsx",
        size_bytes=1,
        blob_name="batches/b-1.xlsx",
        created_at=NOW,
        sha256=SHA,
    )


class Uow:
    def __init__(self, store: FakeConfirmationStore) -> None:
        self.store = store
        self.log = FakeAuditLog()

    @contextmanager
    def __call__(self):  # type: ignore[no-untyped-def]
        class Tx:
            confirmation = self.store
            audit = Auditor(self.log, clock=lambda: NOW)

        yield Tx()


def make(rows: list[StagedForConfirmation], state: str = "in_review", email=EMAIL):  # type: ignore[no-untyped-def]
    store = FakeConfirmationStore(batch=batch(state), staged=rows)
    uow = Uow(store)
    return ConfirmationService(uow, email=lambda: email, clock=lambda: NOW), store, uow


# --- what confirming creates (E-06, RN-03, RN-04) -----------------------------------------------------------


def test_eighty_new_rows_with_twenty_glovo_create_80_incidents_and_60_pending_emails() -> None:
    rows = [source_row(i, "uber eats", f"UE-{i}") for i in range(2, 22)]
    rows += [source_row(i, "just eat", f"JE-{i}") for i in range(22, 62)]
    rows += [source_row(i, "glovo", f"GL-{i}") for i in range(62, 82)]
    assert len(rows) == 80
    service, store, _ = make(rows)
    result = service.confirm("ana", "b-1", SHA)
    assert result["createdIncidents"] == 80
    assert result["pendingEmails"] == 60
    assert result["withoutEmail"] == 20
    assert len(store.incidents) == 80 and len(store.outbox) == 60


def test_glovo_incidents_are_imported_without_email_and_the_others_get_one_each() -> None:
    rows = [
        source_row(2, "uber eats", "A"),
        source_row(3, "just eat", "B"),
        source_row(4, "glovo", "C"),
    ]
    service, store, _ = make(rows)
    service.confirm("ana", "b-1", SHA)
    assert len(store.outbox) == 2
    states = {h["incident"]: h["new"] for h in store.history}
    assert sorted(states.values()) == ["imported_no_email", "pending_send", "pending_send"]


def test_only_new_rows_are_imported() -> None:
    rows = [
        source_row(2, "uber eats", "A"),
        replace(source_row(3, "uber eats", "B"), row_class="duplicate", reason="dup"),
        replace(source_row(4, "uber eats", "C"), row_class="conflict", reason="conf"),
        replace(source_row(5, "uber eats", "D"), row_class="error", reason="bad"),
    ]
    service, store, _ = make(rows)
    result = service.confirm("ana", "b-1", SHA)
    assert result["createdIncidents"] == 1
    assert [(e["rowNumber"], e["class"]) for e in result["excluded"]] == [
        (3, "duplicate"),
        (4, "conflict"),
        (5, "error"),
    ]
    assert len(store.incidents) == 1


def test_the_outbox_keeps_the_authorized_recipient_and_nothing_is_sent() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")])
    service.confirm("ana", "b-1", SHA)
    assert store.outbox == [{"incident": "inc-1", "recipient": "test@example.test"}]


# --- the batch ends confirmed or completed ------------------------------------------------------------------------


def test_a_batch_with_emails_is_confirmed_and_one_without_is_completed() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")])
    service.confirm("ana", "b-1", SHA)
    assert store.finished_state == "confirmed"
    service, store, _ = make([source_row(2, "glovo", "G")])
    service.confirm("ana", "b-1", SHA)
    assert store.finished_state == "completed"


def test_staging_is_cleared_after_confirming() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")])
    service.confirm("ana", "b-1", SHA)
    assert store.staging_cleared


def test_confirming_is_audited_in_the_same_unit_of_work() -> None:
    service, _, uow = make([source_row(2, "uber eats", "A")])
    service.confirm("ana", "b-1", SHA)
    (entry,) = uow.log.entries
    assert (entry.actor, entry.operation, entry.object_id, entry.outcome) == (
        "ana",
        "batch.confirm",
        "b-1",
        "success",
    )
    assert (
        entry.details and entry.details["sha256"] == SHA and entry.details["createdIncidents"] == 1
    )


# --- E-07 and BE-11: idempotency -----------------------------------------------------------------------------------


def test_confirming_again_returns_the_stored_result_and_creates_nothing_new() -> None:
    service, store, uow = make([source_row(2, "uber eats", "A")])
    first = service.confirm("ana", "b-1", SHA)
    second = service.confirm("ana", "b-1", SHA)
    assert first["alreadyConfirmed"] is False and second["alreadyConfirmed"] is True
    assert {k: v for k, v in second.items() if k != "alreadyConfirmed"} == {
        k: v for k, v in first.items() if k != "alreadyConfirmed"
    }
    assert len(store.incidents) == 1 and len(store.outbox) == 1
    assert [e.operation for e in uow.log.entries] == ["batch.confirm"]


def test_a_repeat_does_not_need_the_staging_that_was_cleared() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")])
    service.confirm("ana", "b-1", SHA)
    assert store.staged == []
    assert service.confirm("ana", "b-1", SHA)["createdIncidents"] == 1


# --- BE-02: matches that appear during the review ---------------------------------------------------------------------


def test_a_key_created_meanwhile_is_excluded_and_the_rest_is_imported() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A"), source_row(3, "uber eats", "B")])
    store.incidents[("uber eats", "A")] = ("other", store.staged[0].fields)  # same data
    result = service.confirm("ana", "b-1", SHA)
    assert result["createdIncidents"] == 1
    assert result["excludedAtConfirmation"] == [
        {
            "rowNumber": 2,
            "class": "duplicate",
            "reason": "Otro lote confirmó esta incidencia mientras se revisaba.",
        }
    ]
    assert len(store.outbox) == 1  # none for the overtaken row


def test_a_key_created_meanwhile_with_different_data_is_a_conflict() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A", description="mine")])
    store.incidents[("uber eats", "A")] = ("other", Fields(provider="uber eats", order_id="A"))
    result = service.confirm("ana", "b-1", SHA)
    assert result["excludedAtConfirmation"][0]["class"] == "conflict"
    assert result["createdIncidents"] == 0


# --- who and what may be confirmed ---------------------------------------------------------------------------------------


def test_a_batch_of_another_user_is_not_found() -> None:
    service, _, _ = make([source_row(2, "uber eats", "A")])
    with pytest.raises(BatchNotFound):
        service.confirm("luis", "b-1", SHA)


@pytest.mark.parametrize("state", ["discarded", "uploaded", "processing", "rejected"])
def test_a_batch_that_is_not_under_review_cannot_be_confirmed(state: str) -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")], state=state)
    with pytest.raises(BatchNotConfirmable) as caught:
        service.confirm("ana", "b-1", SHA)
    assert caught.value.discarded is (state == "discarded")
    assert store.incidents == {}


def test_a_different_file_version_is_refused_and_nothing_is_created() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")])
    with pytest.raises(ReviewedVersionMismatch):
        service.confirm("ana", "b-1", "b" * 64)
    assert store.incidents == {} and store.outbox == []


def test_emails_need_the_authorized_recipient() -> None:
    service, store, _ = make([source_row(2, "uber eats", "A")], email=None)
    with pytest.raises(RecipientNotConfigured):
        service.confirm("ana", "b-1", SHA)
    assert store.incidents == {}


def test_a_batch_with_only_glovo_needs_no_recipient() -> None:
    service, _, _ = make([source_row(2, "glovo", "G")], email=None)
    assert service.confirm("ana", "b-1", SHA)["createdIncidents"] == 1


def test_the_confirmation_time_is_the_one_of_the_clock() -> None:
    service, _, _ = make([source_row(2, "uber eats", "A")])
    result = service.confirm("ana", "b-1", SHA)
    assert result["confirmedAt"] == NOW.isoformat().replace("+00:00", "Z")
    assert isinstance(NOW, datetime)
