"""Keeping the confirmed original in the immutable store (ADR-14, RF-19).

Storage cannot take part in the PostgreSQL transaction, so this runs after it: the worker copies
the reviewed file to the confirmed store under a name set by the batch, reads it back and checks its
SHA-256. A mismatch is recorded and alerted; it is never "fixed" by replacing the original.
"""

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Protocol

from app.services.ports import CONFIRMED, UPLOADS, StorageService

LOG = logging.getLogger("app.worker")
BATCHES_PER_TICK = 5


@dataclass(frozen=True)
class PendingCopy:
    batch_id: str
    blob_name: str  # the temporary file in `uploads`
    sha256: str  # the reviewed version


def confirmed_name(batch_id: str) -> str:
    return f"batches/{batch_id}.xlsx"


class OriginalCopyRepository(Protocol):
    def pending(self, limit: int) -> list[PendingCopy]: ...

    def record(self, batch_id: str, status: str, outcome: str, details: dict[str, str]) -> None: ...


class OriginalCopyService:
    def __init__(self, repository: OriginalCopyRepository, storage: StorageService) -> None:
        self._repository = repository
        self._storage = storage

    def process_pending(self) -> int:
        """Copy and verify what is waiting; returns how many reached a final status."""
        finished = 0
        for item in self._repository.pending(BATCHES_PER_TICK):
            try:
                finished += self._copy(item)
            except Exception as exc:  # the store may be unreachable: try again next tick
                LOG.warning(
                    json.dumps(
                        {"event": "original.copy_retry", "batch": item.batch_id, "error": str(exc)}
                    )
                )
        return finished

    def _copy(self, item: PendingCopy) -> int:
        target = confirmed_name(item.batch_id)
        source = self._storage.read_blob(UPLOADS, item.blob_name)
        if hashlib.sha256(source).hexdigest() != item.sha256:
            return self._discrepancy(item, "the temporary file is not the reviewed one")
        self._storage.write_new_blob(CONFIRMED, target, source)  # False when already stored
        stored = self._storage.read_blob(CONFIRMED, target)
        if hashlib.sha256(stored).hexdigest() != item.sha256:
            return self._discrepancy(item, "the stored file is not the reviewed one")
        self._repository.record(
            item.batch_id,
            "verified",
            "success",
            {"sha256": item.sha256, "object": f"{CONFIRMED}/{target}"},
        )
        return 1

    def _discrepancy(self, item: PendingCopy, reason: str) -> int:
        LOG.error(
            json.dumps({"event": "original.discrepancy", "batch": item.batch_id, "reason": reason})
        )
        self._repository.record(
            item.batch_id,
            "discrepancy",
            "failure",
            {"sha256": item.sha256, "reason": reason},
        )
        return 1
