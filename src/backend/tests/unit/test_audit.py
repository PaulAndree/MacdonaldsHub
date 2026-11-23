"""Audit recording (RNF-05): actor, UTC instant, object and outcome for every operation."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.services.audit import Auditor
from app.services.ports import AuditEntry


class FakeLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


NOW = datetime(2026, 11, 23, 10, 30, tzinfo=UTC)


def auditor() -> tuple[Auditor, FakeLog]:
    log = FakeLog()
    return Auditor(log, clock=lambda: NOW), log


def test_an_operation_records_actor_instant_object_and_outcome() -> None:
    audit, log = auditor()
    audit.record("ana@example.test", "batch.confirm", "batch", "b-1", "success", {"incidents": 80})
    (entry,) = log.entries
    assert entry.actor == "ana@example.test"
    assert entry.at == NOW and entry.at.utcoffset() == timedelta(0)
    target = (entry.operation, entry.object_type, entry.object_id)
    assert target == ("batch.confirm", "batch", "b-1")
    assert entry.outcome == "success"
    assert entry.details == {"incidents": 80}


def test_the_system_can_be_the_actor() -> None:
    audit, log = auditor()
    audit.record("system:worker", "batch.process", "batch", "b-1", "success")
    assert log.entries[0].actor == "system:worker"


def test_the_instant_is_always_utc() -> None:
    madrid = timezone(timedelta(hours=1))
    log = FakeLog()
    audit = Auditor(log, clock=lambda: datetime(2026, 11, 23, 11, 30, tzinfo=madrid))
    audit.record("ana", "batch.discard", "batch", "b-1", "success")
    assert log.entries[0].at == NOW
    assert log.entries[0].at.utcoffset() == timedelta(0)


def test_a_naive_clock_is_refused() -> None:
    audit = Auditor(FakeLog(), clock=lambda: datetime(2026, 11, 23, 10, 30))
    with pytest.raises(ValueError):
        audit.record("ana", "batch.discard", "batch", "b-1", "success")


@pytest.mark.parametrize("actor", ["", "   "])
def test_an_operation_without_actor_is_refused(actor: str) -> None:
    audit, log = auditor()
    with pytest.raises(ValueError):
        audit.record(actor, "batch.confirm", "batch", "b-1", "success")
    assert log.entries == []


def test_only_known_outcomes_are_accepted() -> None:
    audit, _ = auditor()
    with pytest.raises(ValueError):
        audit.record("ana", "batch.confirm", "batch", "b-1", "maybe")


def test_an_object_without_identifier_is_allowed() -> None:
    audit, log = auditor()
    audit.record("ana", "session.logout", "user", None, "success")
    assert log.entries[0].object_id is None
