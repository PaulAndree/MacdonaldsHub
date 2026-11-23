"""PostgreSQL side of keeping the confirmed original."""

import uuid

from sqlalchemy import Engine, text

from app.adapters.db.audit import SqlAuditLog
from app.services.audit import Auditor
from app.services.original_copy import PendingCopy

SYSTEM = "system:worker"


class SqlOriginalCopyRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def pending(self, limit: int) -> list[PendingCopy]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id::text, blob_name, sha256 FROM batch "
                    "WHERE state IN ('confirmed', 'completed') AND original_copy = 'pending' "
                    "AND sha256 IS NOT NULL ORDER BY confirmed_at LIMIT :n"
                ),
                {"n": limit},
            )
            return [PendingCopy(*row) for row in rows]

    def record(self, batch_id: str, status: str, outcome: str, details: dict[str, str]) -> None:
        operation = (
            "batch.original_verified" if status == "verified" else "batch.original_discrepancy"
        )
        with self._engine.begin() as conn:
            conn.execute(
                text("UPDATE batch SET original_copy = :s, updated_at = now() WHERE id = :id"),
                {"s": status, "id": uuid.UUID(batch_id)},
            )
            Auditor(SqlAuditLog(conn)).record(
                SYSTEM, operation, "batch", batch_id, outcome, dict(details)
            )
