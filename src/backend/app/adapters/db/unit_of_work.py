"""One PostgreSQL transaction for a use case: its changes and its audit records commit together."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from typing import Any

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from app.adapters.db.audit import SqlAuditLog
from app.services.audit import Auditor
from app.services.batches import BatchRecord, PreparedSummary, UnconfirmedBatchRace

_SELECT = (
    "SELECT b.id::text AS id, b.owner, b.state, b.file_name, b.size_bytes, b.blob_name, "
    "b.created_at, b.sha256, b.rejection_reason, b.rejection_detail, "
    "c.id::text AS identical_batch_id, c.confirmed_at AS identical_confirmed_at "
    "FROM batch b LEFT JOIN batch c ON c.id = b.identical_to_batch"
)


def _record(row: Any) -> BatchRecord:
    return BatchRecord(**row._mapping)


class SqlBatches:
    def __init__(self, connection: Connection) -> None:
        self._c = connection

    def add(self, record: BatchRecord) -> None:
        try:
            with self._c.begin_nested():  # a refusal must not abort the surrounding transaction
                self._c.execute(
                    text(
                        "INSERT INTO batch (id, owner, state, file_name, size_bytes, blob_name, "
                        "created_at) VALUES (:id, :owner, :state, :file_name, :size_bytes, "
                        ":blob_name, :created_at)"
                    ),
                    {
                        "id": uuid.UUID(record.id),
                        "owner": record.owner,
                        "state": record.state,
                        "file_name": record.file_name,
                        "size_bytes": record.size_bytes,
                        "blob_name": record.blob_name,
                        "created_at": record.created_at,
                    },
                )
        except IntegrityError as exc:
            if "uq_batch_one_unconfirmed" in str(exc.orig):
                raise UnconfirmedBatchRace() from None
            raise

    def get_for_owner(self, batch_id: str, owner: str) -> BatchRecord | None:
        try:
            key = uuid.UUID(batch_id)
        except ValueError:
            return None  # not one of ours: it simply does not exist
        row = self._c.execute(
            text(f"{_SELECT} WHERE b.id = :id AND b.owner = :owner"),
            {"id": key, "owner": owner},
        ).first()
        if row is None:
            return None
        record = _record(row)
        return (
            replace(record, summary=self._summary(key)) if record.state == "in_review" else record
        )

    def _summary(self, key: uuid.UUID) -> PreparedSummary:
        counts = self._c.execute(
            text(
                "SELECT count(*) FILTER (WHERE r.class = 'new'), "
                "count(*) FILTER (WHERE r.class = 'duplicate'), "
                "count(*) FILTER (WHERE r.class = 'conflict'), "
                "count(*) FILTER (WHERE r.class = 'error'), "
                "count(*) FILTER (WHERE r.class = 'new' AND p.sends_email), "
                "count(*) FILTER (WHERE r.class = 'new' AND NOT p.sends_email) "
                "FROM batch_row r LEFT JOIN provider p ON p.code = r.provider "
                "WHERE r.batch_id = :id"
            ),
            {"id": key},
        ).one()
        return PreparedSummary(*counts)

    def find_unconfirmed(self, owner: str) -> BatchRecord | None:
        row = self._c.execute(
            text(
                f"{_SELECT} WHERE b.owner = :owner "
                "AND b.state IN ('uploaded', 'processing', 'in_review')"
            ),
            {"owner": owner},
        ).first()
        return _record(row) if row else None

    def lock_for_owner(self, batch_id: str, owner: str) -> BatchRecord | None:
        try:
            key = uuid.UUID(batch_id)
        except ValueError:
            return None
        row = self._c.execute(
            text(f"{_SELECT} WHERE b.id = :id AND b.owner = :owner FOR UPDATE OF b"),
            {"id": key, "owner": owner},
        ).first()
        return _record(row) if row else None

    def lock_unconfirmed(self, owner: str) -> list[BatchRecord]:
        rows = self._c.execute(
            text(
                f"{_SELECT} WHERE b.owner = :owner "
                "AND b.state IN ('uploaded', 'processing', 'in_review') ORDER BY b.created_at "
                "FOR UPDATE OF b"
            ),
            {"owner": owner},
        )
        return [_record(r) for r in rows]

    def discard(self, batch_id: str) -> BatchRecord:
        key = uuid.UUID(batch_id)
        self._c.execute(text("DELETE FROM batch_row WHERE batch_id = :id"), {"id": key})
        self._c.execute(
            text(
                "UPDATE batch SET state = 'discarded', cleanup = 'pending', lease_until = NULL, "
                "updated_at = now() WHERE id = :id"
            ),
            {"id": key},
        )
        return _record(self._c.execute(text(f"{_SELECT} WHERE b.id = :id"), {"id": key}).one())

    def set_state(self, batch_id: str, state: str) -> BatchRecord:
        key = uuid.UUID(batch_id)
        self._c.execute(
            text("UPDATE batch SET state = :state, updated_at = now() WHERE id = :id"),
            {"id": key, "state": state},
        )
        row = self._c.execute(text(f"{_SELECT} WHERE b.id = :id"), {"id": key}).one()
        return _record(row)


class SqlTransaction:
    def __init__(self, connection: Connection) -> None:
        from app.adapters.db.confirmation import SqlConfirmationStore
        from app.adapters.db.incidents import SqlIncidents

        self.batches = SqlBatches(connection)
        self.confirmation = SqlConfirmationStore(connection)
        self.incidents = SqlIncidents(connection)
        self.audit = Auditor(SqlAuditLog(connection))


class SqlUnitOfWork:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def __call__(self) -> Iterator[SqlTransaction]:
        with self._engine.begin() as connection:
            yield SqlTransaction(connection)
