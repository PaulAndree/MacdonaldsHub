"""In-memory stand-ins for the ports, for unit tests of use cases (no database, no storage)."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.services.audit import Auditor
from app.services.batches import BatchRecord, UnconfirmedBatchRace
from app.services.ports import AuditEntry, BlobInfo, UploadGrant

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)


class FakeAuditLog:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def record(self, entry: AuditEntry) -> None:
        self.entries.append(entry)


class FakeBatches:
    UNCONFIRMED = ("uploaded", "processing", "in_review")

    def __init__(self) -> None:
        self.rows: dict[str, BatchRecord] = {}

    def add(self, record: BatchRecord) -> None:
        if any(r.owner == record.owner and r.state in self.UNCONFIRMED for r in self.rows.values()):
            raise UnconfirmedBatchRace()
        self.rows[record.id] = record

    def get_for_owner(self, batch_id: str, owner: str) -> BatchRecord | None:
        row = self.rows.get(batch_id)
        return row if row and row.owner == owner else None

    def find_unconfirmed(self, owner: str) -> BatchRecord | None:
        return next(
            (r for r in self.rows.values() if r.owner == owner and r.state in self.UNCONFIRMED),
            None,
        )

    def set_state(self, batch_id: str, state: str) -> BatchRecord:
        self.rows[batch_id] = replace(self.rows[batch_id], state=state)  # type: ignore[arg-type]
        return self.rows[batch_id]


class FakeTransaction:
    def __init__(self, batches: FakeBatches, log: FakeAuditLog) -> None:
        self.batches = batches
        self.audit = Auditor(log, clock=lambda: NOW)


class FakeUow:
    def __init__(self) -> None:
        self.batches = FakeBatches()
        self.log = FakeAuditLog()

    @contextmanager
    def __call__(self) -> Iterator[FakeTransaction]:
        yield FakeTransaction(self.batches, self.log)


class FakeStorage:
    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], int] = {}
        self.granted: list[str] = []

    def issue_upload_grant(self, blob_name: str) -> UploadGrant:
        self.granted.append(blob_name)
        return UploadGrant(
            blob_name=blob_name,
            url=f"https://storage.example.test/uploads/{blob_name}?sp=c",
            method="PUT",
            headers={"x-ms-blob-type": "BlockBlob", "If-None-Match": "*"},
            expires_at=NOW + timedelta(minutes=15),
        )

    def get_blob_info(self, container: str, blob_name: str) -> BlobInfo | None:
        size = self.blobs.get((container, blob_name))
        return None if size is None else BlobInfo(container, blob_name, size, "etag", None)

    def read_blob(self, container: str, blob_name: str) -> bytes:
        return b""

    def write_new_blob(self, container: str, blob_name: str, data: bytes) -> bool:
        if (container, blob_name) in self.blobs:
            return False
        self.blobs[(container, blob_name)] = len(data)
        return True

    def delete_blob(self, container: str, blob_name: str) -> None:
        self.blobs.pop((container, blob_name), None)
