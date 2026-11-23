"""The email queue as the administrator sees it, and its global pause (RF-14, MAIL-02, MAIL-09)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.clock import utc_now
from app.domain.mail_rules import MIN_INTERVAL_SECONDS, next_eligible_at


@dataclass(frozen=True)
class Totals:
    pending: int
    sending: int
    sent: int
    error: int


@dataclass(frozen=True)
class Control:
    paused: bool
    paused_at: datetime | None
    last_started_at: datetime | None
    in_flight: int


@dataclass(frozen=True)
class BatchProgress:
    batch_id: str
    totals: Totals

    @property
    def completed(self) -> bool:
        """Every email has ended, which is not the same as every email having succeeded."""
        return self.totals.pending == 0 and self.totals.sending == 0


@dataclass(frozen=True)
class QueueEntry:
    id: str
    incident_id: str
    batch_id: str | None  # None for the email of a manual entry
    order_id: str
    provider: str
    state: str
    reason: str | None
    error_kind: str | None
    started_at: datetime | None
    finished_at: datetime | None
    recipient: str


@dataclass(frozen=True)
class Status:
    paused: bool
    paused_at: datetime | None
    in_flight: int
    sending_available: bool
    unavailable_reason: str | None


@dataclass(frozen=True)
class QueueView:
    status: Status
    min_interval_seconds: int
    next_eligible_at: datetime | None
    totals: Totals
    batches: list[BatchProgress]
    items: list[QueueEntry]
    page: int
    page_size: int
    total: int


class QueueRepository(Protocol):
    def control(self) -> Control: ...

    def totals(self) -> Totals: ...

    def batches(self) -> list[BatchProgress]: ...

    def entries(
        self, state: str | None, batch_id: str | None, page: int, size: int
    ) -> tuple[list[QueueEntry], int]: ...

    def set_paused(self, paused: bool, actor: str) -> Control: ...


class QueueService:
    def __init__(
        self,
        repository: QueueRepository,
        unavailable: Callable[[], str | None],
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._unavailable = unavailable
        self._clock = clock

    def _status(self, control: Control) -> Status:
        reason = self._unavailable()
        return Status(control.paused, control.paused_at, control.in_flight, reason is None, reason)

    def view(self, state: str | None, batch_id: str | None, page: int, size: int) -> QueueView:
        control = self._repository.control()
        totals = self._repository.totals()
        items, total = self._repository.entries(state, batch_id, page, size)
        eligible = next_eligible_at(control.paused, control.last_started_at)
        # A time already in the past means the next attempt can start at once: say nothing.
        pending = totals.pending > 0
        upcoming = (
            eligible if eligible is not None and eligible > self._clock() and pending else None
        )
        return QueueView(
            status=self._status(control),
            min_interval_seconds=MIN_INTERVAL_SECONDS,
            next_eligible_at=upcoming,
            totals=totals,
            batches=self._repository.batches(),
            items=items,
            page=page,
            page_size=size,
            total=total,
        )

    def pause(self, actor: str) -> Status:
        return self._status(self._repository.set_paused(True, actor))

    def resume(self, actor: str) -> Status:
        return self._status(self._repository.set_paused(False, actor))
