"""Physical cleanup of the temporary file of finished batches (RF-17, ADR-14).

It removes the uploaded file of a batch that was discarded or rejected, and of a confirmed one only
after its original is stored and verified in the confirmed store. It works with the batch row
locked, so it can never run against a batch while it is being confirmed or discarded, and it never
says a file is removed until the store confirms it is gone.
"""

import json
import logging
from contextlib import AbstractContextManager
from typing import Protocol

from app.services.ports import UPLOADS, StorageService

LOG = logging.getLogger("app.worker")
BATCHES_PER_TICK = 5


class LockedCleanup(Protocol):
    """One batch to clean, held under its row lock until the unit of work ends."""

    blob_name: str

    def done(self) -> None: ...

    def failed(self, error: str) -> None: ...


class CleanupRepository(Protocol):
    def candidates(self, limit: int) -> list[str]: ...

    def locked(self, batch_id: str) -> AbstractContextManager[LockedCleanup | None]: ...


class CleanupService:
    def __init__(self, repository: CleanupRepository, storage: StorageService) -> None:
        self._repository = repository
        self._storage = storage

    def process_pending(self) -> int:
        """Remove what is waiting; returns how many batches were completely cleaned."""
        cleaned = 0
        for batch_id in self._repository.candidates(BATCHES_PER_TICK):
            with self._repository.locked(batch_id) as item:
                if item is None:
                    continue  # no longer eligible, or another unit of work holds it
                try:
                    self._storage.delete_blob(UPLOADS, item.blob_name)
                    if self._storage.get_blob_info(UPLOADS, item.blob_name) is not None:
                        raise OSError("the file is still stored after deleting it")
                except Exception as exc:
                    LOG.warning(
                        json.dumps({"event": "cleanup.retry", "batch": batch_id, "error": str(exc)})
                    )
                    item.failed(str(exc))
                    continue
                item.done()
                cleaned += 1
        return cleaned
