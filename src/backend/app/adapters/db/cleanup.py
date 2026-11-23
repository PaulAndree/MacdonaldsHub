"""PostgreSQL side of cleanup. The batch row stays locked while its file is removed."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import Connection, Engine, text

from app.adapters.db.audit import SqlAuditLog
from app.services.audit import Auditor

SYSTEM = "system:worker"

# A file may go when its batch can never be confirmed (discarded, rejected) or when it was
# confirmed and its original is already stored and verified in the confirmed store.
_ELIGIBLE = (
    "cleanup IN ('pending', 'failed') AND ("
    "state IN ('discarded', 'rejected') OR "
    "(state IN ('confirmed', 'completed') AND original_copy = 'verified'))"
)


@dataclass
class _Locked:
    batch_id: str
    blob_name: str
    connection: Connection

    def done(self) -> None:
        self._finish("done", None, "success")

    def failed(self, error: str) -> None:
        self._finish("failed", error[:500], "failure")

    def _finish(self, status: str, error: str | None, outcome: str) -> None:
        self.connection.execute(
            text(
                "UPDATE batch SET cleanup = :s, cleanup_error = :e, updated_at = now() "
                "WHERE id = :id"
            ),
            {"s": status, "e": error, "id": uuid.UUID(self.batch_id)},
        )
        # No rows and no file name: who removed what, and how it ended.
        Auditor(SqlAuditLog(self.connection)).record(
            SYSTEM, "batch.cleanup", "batch", self.batch_id, outcome, {"status": status}
        )


class SqlCleanupRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def candidates(self, limit: int) -> list[str]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT id::text FROM batch WHERE {_ELIGIBLE} ORDER BY updated_at LIMIT :n"),
                {"n": limit},
            )
            return [r[0] for r in rows]

    @contextmanager
    def locked(self, batch_id: str) -> Iterator[_Locked | None]:
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"SELECT blob_name FROM batch WHERE id = :id AND {_ELIGIBLE} "
                    "FOR UPDATE SKIP LOCKED"
                ),
                {"id": uuid.UUID(batch_id)},
            ).first()
            yield None if row is None else _Locked(batch_id, row[0], conn)
