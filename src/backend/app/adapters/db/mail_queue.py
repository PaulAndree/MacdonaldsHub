"""PostgreSQL reads of the email queue and the writes of pause and resume."""

from sqlalchemy import Engine, text

from app.adapters.db.audit import SqlAuditLog
from app.services.audit import Auditor
from app.services.mail_queue import BatchProgress, Control, QueueEntry, Totals

_STATES = ("pending", "sending", "sent", "error")
_IN_FLIGHT = "(SELECT count(*) FROM outbox WHERE state = 'sending')"


def _totals(rows: list[tuple[str, int]]) -> Totals:
    counts = dict(rows)
    return Totals(*(int(counts.get(s, 0)) for s in _STATES))


class SqlQueueRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def control(self) -> Control:
        with self._engine.connect() as conn:
            row = conn.execute(
                text(
                    f"SELECT paused, paused_at, last_started_at, {_IN_FLIGHT} AS in_flight "
                    "FROM mail_control WHERE id = 1"
                )
            ).one()
        return Control(row.paused, row.paused_at, row.last_started_at, int(row.in_flight))

    def totals(self) -> Totals:
        with self._engine.connect() as conn:
            rows = conn.execute(text("SELECT state, count(*) FROM outbox GROUP BY state")).all()
        return _totals([(r[0], r[1]) for r in rows])

    def batches(self) -> list[BatchProgress]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT batch_id::text, state, count(*) FROM outbox "
                    "WHERE batch_id IS NOT NULL GROUP BY batch_id, state"
                )
            ).all()
            first = {
                r[0]: r[1]
                for r in conn.execute(
                    text(
                        "SELECT batch_id::text, min(created_at) FROM outbox "
                        "WHERE batch_id IS NOT NULL GROUP BY batch_id"
                    )
                )
            }
        grouped: dict[str, list[tuple[str, int]]] = {}
        for batch, state, count in rows:
            grouped.setdefault(batch, []).append((state, count))
        ordered = sorted(grouped, key=lambda b: first[b])
        return [BatchProgress(b, _totals(grouped[b])) for b in ordered]

    def entries(
        self, state: str | None, batch_id: str | None, page: int, size: int
    ) -> tuple[list[QueueEntry], int]:
        where = (
            "(CAST(:state AS text) IS NULL OR o.state = :state) "
            "AND (CAST(:batch AS text) IS NULL OR o.batch_id::text = :batch)"
        )
        params = {"state": state, "batch": batch_id}
        with self._engine.connect() as conn:
            total = conn.execute(
                text(f"SELECT count(*) FROM outbox o WHERE {where}"), params
            ).scalar()
            rows = conn.execute(
                text(
                    "SELECT o.id::text AS id, o.incident_id::text AS incident_id, "
                    "o.batch_id::text AS batch_id, i.order_id, i.provider, o.state, o.reason, "
                    "o.error_kind, o.started_at, o.finished_at, o.recipient "
                    f"FROM outbox o JOIN incident i ON i.id = o.incident_id WHERE {where} "
                    "ORDER BY o.created_at, o.id LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": size, "offset": (page - 1) * size},
            )
            items = [
                QueueEntry(
                    id=r.id,
                    incident_id=r.incident_id,
                    batch_id=r.batch_id,
                    order_id=r.order_id,
                    provider=r.provider,
                    state=r.state,
                    reason=r.reason,
                    error_kind=r.error_kind,
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    recipient=r.recipient,
                )
                for r in rows
            ]
        return items, int(total or 0)

    def set_paused(self, paused: bool, actor: str) -> Control:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE mail_control SET paused = :p, "
                    "paused_at = CASE WHEN :p THEN now() ELSE NULL END, updated_at = now() "
                    "WHERE id = 1"
                ),
                {"p": paused},
            )
            Auditor(SqlAuditLog(conn)).record(
                actor,
                "queue.pause" if paused else "queue.resume",
                "mail_queue",
                "1",
                "success",
                {"paused": paused},
            )
        return self.control()
