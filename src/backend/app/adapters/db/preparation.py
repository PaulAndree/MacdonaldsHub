"""PostgreSQL side of preparing a batch: claiming work, looking up incidents, writing staging."""

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from sqlalchemy import Engine, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.adapters.db.audit import SqlAuditLog
from app.adapters.db.unit_of_work import _SELECT, _record
from app.domain.classification import Existing, Key
from app.domain.rows import Fields
from app.services.audit import Auditor
from app.services.batches import BatchRecord
from app.services.preparation import SYSTEM, StagedRow


class SqlPreparationRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def claim_next(self, now: datetime, lease: timedelta) -> BatchRecord | None:
        """Take one batch to process. A batch whose lease has not ended belongs to a live worker;
        one whose lease has ended (a worker died) can be taken again."""
        with self._engine.begin() as conn:
            found = conn.execute(
                text(
                    "SELECT id FROM batch WHERE state = 'processing' "
                    "AND (lease_until IS NULL OR lease_until < :now) "
                    "ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED"
                ),
                {"now": now},
            ).first()
            if found is None:
                return None
            conn.execute(
                text("UPDATE batch SET lease_until = :until, updated_at = now() WHERE id = :id"),
                {"id": found.id, "until": now + lease},
            )
            return _record(
                conn.execute(text(f"{_SELECT} WHERE b.id = :id"), {"id": found.id}).one()
            )

    def known_branches(self) -> frozenset[str]:
        with self._engine.connect() as conn:
            rows = conn.execute(text("SELECT name FROM branch WHERE active"))
            return frozenset(r[0] for r in rows)

    def existing_incidents(self, keys: Sequence[Key]) -> Mapping[Key, Existing]:
        if not keys:
            return {}
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT i.id::text AS id, i.provider, i.order_id, i.incident_date, "
                    "i.incident_time, i.branch, i.claim_amount, i.provider_costs, i.total, "
                    "i.description FROM incident i JOIN unnest(CAST(:providers AS text[]), "
                    "CAST(:orders AS text[])) AS k(provider, order_id) "
                    "ON i.provider = k.provider AND i.order_id = k.order_id"
                ),
                {"providers": [k[0] for k in keys], "orders": [k[1] for k in keys]},
            )
            return {
                (r.provider, r.order_id): Existing(
                    r.id,
                    Fields(
                        provider=r.provider,
                        order_id=r.order_id,
                        incident_date=r.incident_date,
                        incident_time=r.incident_time,
                        branch=r.branch,
                        claim_amount=r.claim_amount,
                        provider_costs=r.provider_costs,
                        total=r.total,
                        description=r.description,
                    ),
                )
                for r in rows
            }

    def find_confirmed_with_hash(self, sha256: str) -> str | None:
        with self._engine.connect() as conn:
            return conn.execute(
                text(
                    "SELECT id::text FROM batch WHERE sha256 = :h "
                    "AND state IN ('confirmed', 'completed') ORDER BY confirmed_at DESC LIMIT 1"
                ),
                {"h": sha256},
            ).scalar()

    def save_prepared(
        self,
        batch_id: str,
        sha256: str,
        rows: Sequence[StagedRow],
        identical_to: str | None,
        now: datetime,
    ) -> bool:
        key = uuid.UUID(batch_id)
        with self._engine.begin() as conn:
            if not self._still_processing(conn, key):
                return False  # discarded meanwhile: leave it alone
            conn.execute(
                text("DELETE FROM batch_row WHERE batch_id = :b"), {"b": key}
            )  # repeatable
            if rows:
                conn.execute(
                    text(
                        "INSERT INTO batch_row (batch_id, row_number, class, reason, provider, "
                        "order_id, incident_date, incident_time, branch, claim_amount, "
                        "provider_costs, total, description, existing_incident_id, raw) VALUES "
                        "(:b, :n, :c, :r, :provider, :order_id, :date, :time, :branch, :claim, "
                        ":costs, :total, :description, :existing, :raw)"
                    ).bindparams(bindparam("raw", type_=JSONB)),
                    [
                        {
                            "b": key,
                            "n": r.row_number,
                            "c": r.row_class,
                            "r": r.reason,
                            "provider": r.fields.provider,
                            "order_id": r.fields.order_id,
                            "date": r.fields.incident_date,
                            "time": r.fields.incident_time,
                            "branch": r.fields.branch,
                            "claim": r.fields.claim_amount,
                            "costs": r.fields.provider_costs,
                            "total": r.fields.total,
                            "description": r.fields.description,
                            "raw": dict(r.raw),
                            "existing": uuid.UUID(r.existing_incident_id)
                            if r.existing_incident_id
                            else None,
                        }
                        for r in rows
                    ],
                )
            conn.execute(
                text(
                    "UPDATE batch SET state = 'in_review', sha256 = :h, lease_until = NULL, "
                    "identical_to_batch = :same, updated_at = now() WHERE id = :id"
                ),
                {"id": key, "h": sha256, "same": uuid.UUID(identical_to) if identical_to else None},
            )
            totals = {
                c: sum(1 for r in rows if r.row_class == c)
                for c in ("new", "duplicate", "conflict", "error")
            }
            Auditor(SqlAuditLog(conn), clock=lambda: now).record(
                SYSTEM, "batch.prepare", "batch", batch_id, "success", {"rows": len(rows), **totals}
            )
        return True

    def save_rejected(
        self, batch_id: str, reason: str, detail: str | None, sha256: str | None
    ) -> bool:
        key = uuid.UUID(batch_id)
        with self._engine.begin() as conn:
            if not self._still_processing(conn, key):
                return False
            conn.execute(text("DELETE FROM batch_row WHERE batch_id = :b"), {"b": key})
            conn.execute(
                text(
                    "UPDATE batch SET state = 'rejected', rejection_reason = :r, "
                    "rejection_detail = :d, sha256 = :h, lease_until = NULL, updated_at = now() "
                    "WHERE id = :id"
                ),
                {"id": key, "r": reason, "d": detail, "h": sha256},
            )
            Auditor(SqlAuditLog(conn)).record(
                SYSTEM, "batch.reject", "batch", batch_id, "success", {"reason": reason}
            )
        return True

    @staticmethod
    def _still_processing(conn, key: uuid.UUID) -> bool:  # type: ignore[no-untyped-def]
        state = conn.execute(
            text("SELECT state FROM batch WHERE id = :id FOR UPDATE"), {"id": key}
        ).scalar()
        return bool(state == "processing")
