"""PostgreSQL side of sending. Every method is one short transaction; the call to the mail service
is never made inside one."""

import uuid
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.adapters.db.audit import SqlAuditLog
from app.domain.mail_rules import can_start, recipient_authorized
from app.services.audit import Auditor
from app.services.email_sending import UNVERIFIED_REASON, Attempt

SYSTEM = "system:worker"
NOT_AUTHORIZED = "Destinatario no autorizado: el correo no se envió."


class SqlSendingRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # --- recovery ---

    def recover_interrupted(self) -> int:
        """A tick is synchronous, so an email found Enviando at its start belongs to a process that
        stopped. It ends in Error as unverified and is never sent again."""
        with self._engine.begin() as conn:
            ids = [
                str(r[0])
                for r in conn.execute(
                    text(
                        "SELECT id FROM outbox WHERE state = 'sending' "
                        "ORDER BY started_at FOR UPDATE SKIP LOCKED"
                    )
                )
            ]
            for email_id in ids:
                _end(
                    conn,
                    email_id,
                    "error",
                    "interrupted_unverified",
                    UNVERIFIED_REASON,
                    "email.recovered",
                )
        return len(ids)

    # --- starting an attempt ---

    def claim(self, authorized_recipient: str | None) -> Attempt | None:
        with self._engine.begin() as conn:
            control = conn.execute(
                text(
                    "SELECT paused, last_started_at, now() AS db_now "
                    "FROM mail_control WHERE id = 1 FOR UPDATE"
                )
            ).one()
            # The database's own clock decides, so that no host's clock can shorten the interval.
            if not can_start(control.paused, control.last_started_at, control.db_now):
                return None
            found = conn.execute(
                text(
                    "SELECT o.id::text AS id, o.recipient, o.subject, o.body, i.order_id "
                    "FROM outbox o JOIN incident i ON i.id = o.incident_id "
                    "JOIN provider p ON p.code = i.provider "
                    "WHERE o.state = 'pending' AND p.sends_email "
                    "ORDER BY o.created_at, o.id LIMIT 1 FOR UPDATE OF o SKIP LOCKED"
                )
            ).first()
            if found is None:
                return None
            if not recipient_authorized(found.recipient, authorized_recipient):
                # No call is made, so it is not an attempt: the interval is not consumed.
                _end(conn, found.id, "error", "send_failed", NOT_AUTHORIZED, "email.refused")
                return None
            conn.execute(
                text("UPDATE outbox SET state = 'sending', started_at = :now WHERE id = :id"),
                {"id": uuid.UUID(found.id), "now": control.db_now},
            )
            conn.execute(
                text(
                    "UPDATE mail_control SET last_started_at = :now, "
                    "updated_at = now() WHERE id = 1"
                ),
                {"now": control.db_now},
            )
            Auditor(SqlAuditLog(conn)).record(
                SYSTEM, "email.attempt_started", "email", found.id, "success", None
            )
            return Attempt(found.id, found.order_id, found.recipient, found.subject, found.body)

    # --- results ---

    def finish_sent(self, email_id: str) -> bool:
        with self._engine.begin() as conn:
            return _end(conn, email_id, "sent", None, None, "email.sent")

    def finish_error(self, email_id: str, kind: str, reason: str) -> bool:
        with self._engine.begin() as conn:
            return _end(conn, email_id, "error", kind, reason, "email.failed")


def _end(
    conn: Connection,
    email_id: str,
    state: str,
    kind: str | None,
    reason: str | None,
    operation: str,
) -> bool:
    """End an email in one transaction: its record, its incident, the history, the batch and the
    audit. Guarded by the state, so a late result cannot overwrite what recovery decided."""
    key = uuid.UUID(email_id)
    ended: Any = conn.execute(
        text(
            "UPDATE outbox SET state = :state, finished_at = now(), reason = :reason, "
            "error_kind = :kind WHERE id = :id AND state IN ('sending', 'pending') "
            "RETURNING incident_id, batch_id"
        ),
        {"id": key, "state": state, "reason": reason, "kind": kind},
    ).first()
    if ended is None:
        return False
    incident_id, batch_id = ended
    if state == "sent":
        today = conn.execute(text("SELECT (now() AT TIME ZONE 'Europe/Madrid')::date")).scalar()
        moved = conn.execute(
            text(
                "UPDATE incident SET state = 'claimed', claim_date = :d "
                "WHERE id = :i AND state = 'pending_send'"
            ),
            {"i": incident_id, "d": today},
        ).rowcount
        if moved:
            _history(conn, incident_id, "status", "pending_send", "claimed", None)
            _history(conn, incident_id, "claimDate", None, str(today), None)
    else:
        moved = conn.execute(
            text(
                "UPDATE incident SET state = 'send_error' WHERE id = :i AND state = 'pending_send'"
            ),
            {"i": incident_id},
        ).rowcount
        if moved:
            _history(conn, incident_id, "status", "pending_send", "send_error", reason)
    if batch_id is not None:
        _complete_batch(conn, batch_id)
    details = {"incident": str(incident_id)}
    if kind:
        details["kind"] = kind
    Auditor(SqlAuditLog(conn)).record(
        SYSTEM, operation, "email", email_id, "success" if state == "sent" else "failure", details
    )
    return True


def _history(
    conn: Connection,
    incident_id: Any,
    field: str,
    previous: str | None,
    new: str | None,
    reason: str | None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO incident_history (incident_id, actor, kind, field, previous, new, reason) "
            "VALUES (:i, 'system', 'email_result', :f, :p, :n, :r)"
        ),
        {"i": incident_id, "f": field, "p": previous, "n": new, "r": reason},
    )


def _complete_batch(conn: Connection, batch_id: Any) -> None:
    """Completado when no email of the batch is left Pendiente or Enviando (not "all succeeded")."""
    open_emails = conn.execute(
        text("SELECT count(*) FROM outbox WHERE batch_id = :b AND state IN ('pending', 'sending')"),
        {"b": batch_id},
    ).scalar()
    if open_emails == 0:
        done = conn.execute(
            text(
                "UPDATE batch SET state = 'completed', updated_at = now() "
                "WHERE id = :b AND state = 'confirmed'"
            ),
            {"b": batch_id},
        ).rowcount
        if done:
            Auditor(SqlAuditLog(conn)).record(
                SYSTEM, "batch.complete", "batch", str(batch_id), "success", None
            )
