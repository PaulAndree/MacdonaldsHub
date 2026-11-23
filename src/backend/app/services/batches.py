"""Batches: registering one, granting its upload and recording that the file arrived (RF-01, RF-03).

The browser never names the blob: the server picks it, and a user can only reach their own batches.
Processing the file belongs to the worker; this module only asks for it.
"""

import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.clock import utc_now
from app.services.audit import Auditor
from app.services.ports import UPLOADS, StorageService, UploadGrant

UNCONFIRMED_STATES = ("uploaded", "processing", "in_review")


class BatchNotFound(Exception):
    """No such batch for this user (another user's batch looks the same: nothing is revealed)."""


class UploadNotFound(Exception):
    """The file of the batch is not in storage."""


class BatchAlreadyConfirmed(Exception):
    """A confirmed batch cannot be cancelled or undone."""


class UnconfirmedBatchRace(Exception):
    """The database refused a second unconfirmed batch of the same user."""


class UnconfirmedBatchExists(Exception):
    """The user already has an unconfirmed batch (one per user, RF-17)."""

    def __init__(self, batch_id: str) -> None:
        super().__init__(batch_id)
        self.batch_id = batch_id


@dataclass(frozen=True)
class PreparedSummary:
    """What a prepared batch holds. Nothing here is definitive until the batch is confirmed."""

    new: int
    duplicate: int
    conflict: int
    error: int
    emails_to_generate: int  # new Uber Eats and Just Eat rows
    without_email: int  # new rows that generate no email (Glovo)


@dataclass(frozen=True)
class BatchRecord:
    id: str
    owner: str
    state: str
    file_name: str
    size_bytes: int
    blob_name: str
    created_at: datetime
    sha256: str | None = None
    rejection_reason: str | None = None
    rejection_detail: str | None = None
    identical_batch_id: str | None = None  # a confirmed batch with the same file (RN-11)
    identical_confirmed_at: datetime | None = None
    summary: PreparedSummary | None = None  # only while the batch is under review


class BatchRepository(Protocol):
    def add(self, record: BatchRecord) -> None: ...

    def get_for_owner(self, batch_id: str, owner: str) -> BatchRecord | None: ...

    def find_unconfirmed(self, owner: str) -> BatchRecord | None: ...

    def lock_for_owner(self, batch_id: str, owner: str) -> BatchRecord | None:
        """Take the batch row, so a confirmation or a cleanup waits for this unit of work."""
        ...

    def lock_unconfirmed(self, owner: str) -> list[BatchRecord]: ...

    def discard(self, batch_id: str) -> BatchRecord:
        """Make it unconfirmable, drop its prepared rows and queue the removal of its file."""
        ...

    def set_state(self, batch_id: str, state: str) -> BatchRecord: ...


class Transaction(Protocol):
    """Everything one unit of work touches. Changes and their audit records commit together."""

    @property
    def batches(self) -> BatchRepository: ...

    @property
    def audit(self) -> Auditor: ...


class UnitOfWork(Protocol):
    def __call__(self) -> AbstractContextManager[Transaction]: ...


class BatchService:
    def __init__(
        self,
        uow: UnitOfWork,
        storage: StorageService,
        clock: Callable[[], datetime] = utc_now,
        new_id: Callable[[], str] = lambda: str(uuid.uuid4()),
    ) -> None:
        self._uow = uow
        self._storage = storage
        self._clock = clock
        self._new_id = new_id

    def create(
        self, owner: str, file_name: str, size_bytes: int
    ) -> tuple[BatchRecord, UploadGrant]:
        batch_id = self._new_id()
        record = BatchRecord(
            id=batch_id,
            owner=owner,
            state="uploaded",
            file_name=file_name,
            size_bytes=size_bytes,
            blob_name=f"batches/{batch_id}.xlsx",  # chosen here, never by the browser
            created_at=self._clock(),
        )
        try:
            with self._uow() as tx:
                pending = tx.batches.find_unconfirmed(owner)
                if pending is not None:
                    raise UnconfirmedBatchExists(pending.id)
                tx.batches.add(record)
                tx.audit.record(owner, "batch.create", "batch", batch_id, "success")
        except UnconfirmedBatchRace:
            # Two requests at once: the database let only one in. Name the one that won.
            with self._uow() as tx:
                winner = tx.batches.find_unconfirmed(owner)
            raise UnconfirmedBatchExists(winner.id if winner else "") from None
        return record, self._storage.issue_upload_grant(record.blob_name)

    def get(self, owner: str, batch_id: str) -> BatchRecord:
        with self._uow() as tx:
            record = tx.batches.get_for_owner(batch_id, owner)
        if record is None:
            raise BatchNotFound(batch_id)
        return record

    def pending(self, owner: str) -> BatchRecord | None:
        """The user's unconfirmed batch, if any. There is no expiry (RF-17)."""
        with self._uow() as tx:
            found = tx.batches.find_unconfirmed(owner)
            return tx.batches.get_for_owner(found.id, owner) if found else None

    def discard(self, owner: str, batch_id: str) -> BatchRecord:
        """Cancel a batch before confirming it (RF-17). Allowed in every unconfirmed state."""
        with self._uow() as tx:
            record = tx.batches.lock_for_owner(batch_id, owner)
            if record is None:
                raise BatchNotFound(batch_id)
            if record.state in ("confirmed", "completed"):
                raise BatchAlreadyConfirmed(batch_id)
            if record.state == "discarded":
                return record
            discarded = tx.batches.discard(batch_id)
            # The audit of a discard holds no rows and no file: only who, when and which batch.
            tx.audit.record(
                owner, "batch.discard", "batch", batch_id, "success", {"previous": record.state}
            )
            return discarded

    def discard_unconfirmed(self, owner: str) -> list[str]:
        """What Cerrar sesión calls: discard the user's unconfirmed batches, and nothing else."""
        with self._uow() as tx:
            ids = []
            for record in tx.batches.lock_unconfirmed(owner):
                tx.batches.discard(record.id)
                tx.audit.record(
                    owner,
                    "batch.discard",
                    "batch",
                    record.id,
                    "success",
                    {"previous": record.state},
                )
                ids.append(record.id)
            return ids

    def complete_upload(self, owner: str, batch_id: str) -> BatchRecord:
        """The browser says the upload finished: check the file is there and ask for processing."""
        with self._uow() as tx:
            record = tx.batches.get_for_owner(batch_id, owner)
            if record is None or record.state not in ("uploaded", "processing"):
                raise BatchNotFound(batch_id)
            if record.state == "processing":
                return record  # asked before: nothing more to do
            if self._storage.get_blob_info(UPLOADS, record.blob_name) is None:
                raise UploadNotFound(batch_id)
            updated = tx.batches.set_state(batch_id, "processing")
            tx.audit.record(owner, "batch.upload_complete", "batch", batch_id, "success")
            return updated
