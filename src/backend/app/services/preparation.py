"""Preparing an uploaded file into staging (RF-03, RF-04): read, validate, classify, stage.

Nothing here creates an incident or an outbox record: the result is only staging rows that the
administrator reviews. The work is safe to repeat, so a worker that restarts can pick it up again.
"""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from app.adapters.xlsx.reader import MAX_FILE_BYTES, XlsxRejected, read_xlsx
from app.domain.classification import Classified, Existing, Key, SourceRow, classify
from app.domain.clock import utc_now
from app.domain.rows import Fields, read_row
from app.services.batches import BatchRecord
from app.services.ports import UPLOADS, StorageService

LEASE = timedelta(minutes=5)
BATCHES_PER_TICK = 5
SYSTEM = "system:worker"


@dataclass(frozen=True)
class StagedRow:
    row_number: int
    row_class: str
    reason: str
    fields: Fields
    existing_incident_id: str | None
    raw: Mapping[str, str | None]  # what each cell said, to show an invalid row as it was


class PreparationRepository(Protocol):
    def claim_next(self, now: datetime, lease: timedelta) -> BatchRecord | None: ...

    def known_branches(self) -> frozenset[str]: ...

    def existing_incidents(self, keys: Sequence[Key]) -> Mapping[Key, Existing]: ...

    def find_confirmed_with_hash(self, sha256: str) -> str | None: ...

    def save_prepared(
        self,
        batch_id: str,
        sha256: str,
        rows: Sequence[StagedRow],
        identical_to: str | None,
        now: datetime,
    ) -> bool: ...

    def save_rejected(
        self, batch_id: str, reason: str, detail: str | None, sha256: str | None
    ) -> bool: ...


class PreparationService:
    def __init__(
        self,
        repository: PreparationRepository,
        storage: StorageService,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._clock = clock

    def process_pending(self) -> int:
        """Prepare the batches waiting to be processed; returns how many were handled."""
        handled = 0
        while handled < BATCHES_PER_TICK:
            batch = self._repository.claim_next(self._clock(), LEASE)
            if batch is None:
                break
            self._process(batch)
            handled += 1
        return handled

    def _process(self, batch: BatchRecord) -> None:
        sha256: str | None = None
        try:
            info = self._storage.get_blob_info(UPLOADS, batch.blob_name)
            if info is None:
                raise XlsxRejected(
                    "corrupt_or_protected_file", "No se encuentra el archivo subido."
                )
            if info.size > MAX_FILE_BYTES:
                raise XlsxRejected(
                    "corrupt_or_protected_file", "El archivo supera el límite de 10 MB."
                )
            content = self._storage.read_blob(UPLOADS, batch.blob_name)
            sha256 = hashlib.sha256(content).hexdigest()
            sheet = read_xlsx(content)
        except XlsxRejected as rejection:
            self._repository.save_rejected(batch.id, rejection.reason, rejection.detail, sha256)
            return

        branches = self._repository.known_branches()
        results = [(row.row_number, read_row(row.cells, branches)) for row in sheet.rows]
        keys = sorted(
            {
                (r.fields.provider, r.fields.order_id)
                for _, r in results
                if r.valid and r.fields.provider and r.fields.order_id
            }
        )
        existing = self._repository.existing_incidents(keys)
        verdicts = classify([SourceRow(n, r) for n, r in results], existing)
        fields_by_row = {n: r.fields for n, r in results}
        raw_by_row = {
            row.row_number: {name: cell.display() for name, cell in row.cells.items()}
            for row in sheet.rows
        }
        staged = [
            _stage(v, fields_by_row[v.row_number], raw_by_row[v.row_number]) for v in verdicts
        ]
        identical = self._repository.find_confirmed_with_hash(sha256)
        self._repository.save_prepared(batch.id, sha256, staged, identical, self._clock())


def _stage(verdict: Classified, fields: Fields, raw: Mapping[str, str | None]) -> StagedRow:
    return StagedRow(
        verdict.row_number, verdict.row_class, verdict.reason, fields, verdict.existing_id, raw
    )
