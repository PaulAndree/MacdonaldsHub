"""In-memory confirmation store: just enough behavior to test the use case without a database."""

import itertools
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from app.domain.rows import Fields
from app.services.batches import BatchRecord
from app.services.confirmation import AuthorizedEmail, StagedForConfirmation

CONFIRMED = ("confirmed", "completed")


@dataclass
class FakeConfirmationStore:
    batch: BatchRecord | None = None
    staged: list[StagedForConfirmation] = field(default_factory=list)
    incidents: dict[tuple[str, str], tuple[str, Fields]] = field(default_factory=dict)
    outbox: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    finished_state: str | None = None
    staging_cleared: bool = False
    fail_on_outbox: bool = False
    ids: Any = field(default_factory=lambda: itertools.count(1))

    def lock_batch(self, batch_id: str, owner: str) -> BatchRecord | None:
        if self.batch and self.batch.id == batch_id and self.batch.owner == owner:
            return self.batch
        return None

    def stored_result(self, batch_id: str) -> dict[str, Any] | None:
        return self.result

    def staged_rows(self, batch_id: str) -> list[StagedForConfirmation]:
        return list(self.staged)

    def insert_incident(
        self, batch_id: str, row: StagedForConfirmation, actor: str, state: str
    ) -> str | None:
        key = (row.fields.provider or "", row.fields.order_id or "")
        if key in self.incidents:
            return None
        incident_id = f"inc-{next(self.ids)}"
        self.incidents[key] = (incident_id, row.fields)
        self.history.append({"incident": incident_id, "new": state, "actor": actor})
        return incident_id

    def existing_fields(self, provider: str, order_id: str) -> Fields | None:
        found = self.incidents.get((provider, order_id))
        return found[1] if found else None

    def add_outbox(self, incident_id: str, batch_id: str, email: AuthorizedEmail) -> None:
        if self.fail_on_outbox:
            raise RuntimeError("the database failed while writing the outbox")
        self.outbox.append({"incident": incident_id, "recipient": email.recipient})

    def finish(
        self, batch_id: str, state: str, result: dict[str, Any], actor: str, now: datetime
    ) -> None:
        self.finished_state = state
        self.result = result
        assert self.batch is not None
        self.batch = replace(self.batch, state=state)
        self.staged = []
        self.staging_cleared = True


def source_row(number: int, provider: str, order_id: str, **over: Any) -> StagedForConfirmation:
    from datetime import date

    base = dict(
        provider=provider,
        order_id=order_id,
        incident_date=date(2026, 11, 2),
        incident_time=None,
        branch=None,
        claim_amount=None,
        provider_costs=None,
        total=None,
        description=None,
    )
    sends = provider in ("uber eats", "just eat")
    return StagedForConfirmation(number, "new", "", Fields(**{**base, **over}), sends)
