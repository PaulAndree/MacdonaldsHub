"""Confirming a reviewed batch (RF-07..RF-10): one atomic, idempotent unit of work.

Inside one transaction: lock the batch, recheck its state, import only the new rows, create one
pending outbox record per Uber Eats or Just Eat incident, store the result and audit it. A failure
anywhere rolls everything back. Nothing is sent: sending belongs to a later change.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.domain.classification import relevant
from app.domain.clock import utc_now
from app.domain.rows import Fields
from app.services.audit import Auditor
from app.services.batches import BatchNotFound, BatchRecord

OVERTAKEN = "Otro lote confirmó esta incidencia mientras se revisaba."


class BatchNotConfirmable(Exception):
    """The batch is not under review (discarded, still processing, rejected...)."""

    def __init__(self, state: str) -> None:
        super().__init__(state)
        self.state = state
        self.discarded = state == "discarded"


class ReviewedVersionMismatch(Exception):
    """The version the user reviewed is not the file that was uploaded."""


class RecipientNotConfigured(Exception):
    """Emails would be created but no authorized recipient is configured (P-01)."""


@dataclass(frozen=True)
class AuthorizedEmail:
    """The recipient and template authorized at confirmation. Never a secret."""

    recipient: str
    template_version: str
    subject: str
    body: str  # with {orderId} as the only variable


@dataclass(frozen=True)
class StagedForConfirmation:
    row_number: int
    row_class: str
    reason: str
    fields: Fields
    sends_email: bool  # the provider generates email (Uber Eats, Just Eat)


class ConfirmationStore(Protocol):
    def lock_batch(self, batch_id: str, owner: str) -> BatchRecord | None: ...

    def stored_result(self, batch_id: str) -> dict[str, Any] | None: ...

    def staged_rows(self, batch_id: str) -> list[StagedForConfirmation]: ...

    def insert_incident(
        self, batch_id: str, row: StagedForConfirmation, actor: str, state: str
    ) -> str | None:
        """Create the incident; None when its key already exists (another batch got there)."""
        ...

    def existing_fields(self, provider: str, order_id: str) -> Fields | None: ...

    def add_outbox(self, incident_id: str, batch_id: str, email: AuthorizedEmail) -> None: ...

    def finish(
        self, batch_id: str, state: str, result: dict[str, Any], actor: str, now: datetime
    ) -> None: ...


class ConfirmationTransaction(Protocol):
    @property
    def confirmation(self) -> ConfirmationStore: ...

    @property
    def audit(self) -> Auditor: ...


class ConfirmationUnitOfWork(Protocol):
    def __call__(self) -> AbstractContextManager[ConfirmationTransaction]: ...


class ConfirmationService:
    def __init__(
        self,
        uow: ConfirmationUnitOfWork,
        email: Callable[[], AuthorizedEmail | None],
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._uow = uow
        self._email = email
        self._clock = clock

    def confirm(self, owner: str, batch_id: str, reviewed_version: str) -> dict[str, Any]:
        with self._uow() as tx:
            store = tx.confirmation
            batch = store.lock_batch(batch_id, owner)  # one confirmation at a time per batch
            if batch is None:
                raise BatchNotFound(batch_id)
            if batch.state in ("confirmed", "completed"):
                stored = store.stored_result(batch_id)
                if stored is not None:
                    return {**stored, "alreadyConfirmed": True}  # no staging, no new effects
            if batch.state != "in_review":
                raise BatchNotConfirmable(batch.state)
            if batch.sha256 != reviewed_version:
                raise ReviewedVersionMismatch(batch_id)

            rows = store.staged_rows(batch_id)
            new_rows = [r for r in rows if r.row_class == "new"]
            email = self._email() if any(r.sends_email for r in new_rows) else None
            if any(r.sends_email for r in new_rows) and email is None:
                raise RecipientNotConfigured(batch_id)

            created = emails = no_email = 0
            overtaken: list[dict[str, Any]] = []
            for row in new_rows:
                state = "pending_send" if row.sends_email else "imported_no_email"
                incident_id = store.insert_incident(batch_id, row, owner, state)
                if incident_id is None:
                    overtaken.append(self._overtaken(store, row))
                    continue
                created += 1
                if row.sends_email and email is not None:
                    store.add_outbox(incident_id, batch_id, email)
                    emails += 1
                else:
                    no_email += 1

            now = self._clock()
            result: dict[str, Any] = {
                "batchId": batch_id,
                "confirmedAt": now.isoformat().replace("+00:00", "Z"),
                "createdIncidents": created,
                "pendingEmails": emails,
                "withoutEmail": no_email,
                "excluded": [
                    {"rowNumber": r.row_number, "class": r.row_class, "reason": r.reason}
                    for r in rows
                    if r.row_class != "new"
                ],
                "excludedAtConfirmation": overtaken,
                "alreadyConfirmed": False,
            }
            # A batch with no email to wait for is complete at once (RF-11).
            store.finish(batch_id, "confirmed" if emails else "completed", result, owner, now)
            tx.audit.record(
                owner,
                "batch.confirm",
                "batch",
                batch_id,
                "success",
                {
                    "sha256": batch.sha256,
                    "createdIncidents": created,
                    "pendingEmails": emails,
                    "withoutEmail": no_email,
                    "excluded": len(result["excluded"]),
                    "excludedAtConfirmation": len(overtaken),
                },
            )
            return result

    @staticmethod
    def _overtaken(store: ConfirmationStore, row: StagedForConfirmation) -> dict[str, Any]:
        """A key another batch created meanwhile: same data is a duplicate, otherwise a conflict."""
        fields = row.fields
        assert fields.provider is not None and fields.order_id is not None
        stored = store.existing_fields(fields.provider, fields.order_id)
        same = stored is not None and relevant(stored) == relevant(fields)
        return {
            "rowNumber": row.row_number,
            "class": "duplicate" if same else "conflict",
            "reason": OVERTAKEN,
        }
