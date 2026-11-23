"""PostgreSQL side of confirming a batch. Every method runs inside the caller's transaction."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB

from app.adapters.db.unit_of_work import _SELECT, _record
from app.domain.rows import Fields
from app.services.batches import BatchRecord
from app.services.confirmation import AuthorizedEmail, StagedForConfirmation


class SqlConfirmationStore:
    def __init__(self, connection: Connection) -> None:
        self._c = connection

    def lock_batch(self, batch_id: str, owner: str) -> BatchRecord | None:
        """Take the batch row. Another confirmation, or a cleanup, waits here until we commit."""
        try:
            key = uuid.UUID(batch_id)
        except ValueError:
            return None
        row = self._c.execute(
            text(f"{_SELECT} WHERE b.id = :id AND b.owner = :owner FOR UPDATE OF b"),
            {"id": key, "owner": owner},
        ).first()
        return _record(row) if row else None

    def stored_result(self, batch_id: str) -> dict[str, Any] | None:
        result = self._c.execute(
            text("SELECT result FROM batch WHERE id = :id"), {"id": uuid.UUID(batch_id)}
        ).scalar()
        return dict(result) if result else None

    def staged_rows(self, batch_id: str) -> list[StagedForConfirmation]:
        rows = self._c.execute(
            text(
                "SELECT r.row_number, r.class, r.reason, r.provider, r.order_id, r.incident_date, "
                "r.incident_time, r.branch, r.claim_amount, r.provider_costs, r.total, "
                "r.description, coalesce(p.sends_email, false) AS sends_email "
                "FROM batch_row r LEFT JOIN provider p ON p.code = r.provider "
                "WHERE r.batch_id = :b ORDER BY r.row_number"
            ),
            {"b": uuid.UUID(batch_id)},
        )
        return [
            StagedForConfirmation(
                row_number=r.row_number,
                row_class=r._mapping["class"],
                reason=r.reason or "",
                fields=Fields(
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
                sends_email=r.sends_email,
            )
            for r in rows
        ]

    def insert_incident(
        self, batch_id: str, row: StagedForConfirmation, actor: str, state: str
    ) -> str | None:
        f = row.fields
        found = self._c.execute(
            text(
                "INSERT INTO incident (provider, order_id, incident_date, incident_time, branch, "
                "claim_amount, provider_costs, total, description, state, batch_id, source, "
                "created_by) VALUES (:provider, :order_id, :date, :time, :branch, :claim, "
                ":costs, :total, :description, :state, :batch, 'import', :actor) "
                "ON CONFLICT (provider, order_id) DO NOTHING RETURNING id"
            ),
            {
                "provider": f.provider,
                "order_id": f.order_id,
                "date": f.incident_date,
                "time": f.incident_time,
                "branch": f.branch,
                "claim": f.claim_amount,
                "costs": f.provider_costs,
                "total": f.total,
                "description": f.description,
                "state": state,
                "batch": uuid.UUID(batch_id),
                "actor": actor,
            },
        ).scalar()
        if found is None:
            return None
        self._c.execute(
            text(
                "INSERT INTO incident_history (incident_id, actor, kind, new) "
                "VALUES (:i, :actor, 'imported', :state)"
            ),
            {"i": found, "actor": actor, "state": state},
        )
        return str(found)

    def existing_fields(self, provider: str, order_id: str) -> Fields | None:
        r = self._c.execute(
            text(
                "SELECT provider, order_id, incident_date, incident_time, branch, claim_amount, "
                "provider_costs, total, description FROM incident "
                "WHERE provider = :p AND order_id = :o"
            ),
            {"p": provider, "o": order_id},
        ).first()
        return None if r is None else Fields(**r._mapping)

    def add_outbox(self, incident_id: str, batch_id: str, email: AuthorizedEmail) -> None:
        self._c.execute(
            text(
                "INSERT INTO outbox (incident_id, batch_id, state, recipient, template_version, "
                "subject, body) VALUES (:i, :b, 'pending', :recipient, :version, :subject, :body)"
            ),
            {
                "i": uuid.UUID(incident_id),
                "b": uuid.UUID(batch_id),
                "recipient": email.recipient,
                "version": email.template_version,
                "subject": email.subject,
                "body": email.body,
            },
        )

    def finish(
        self, batch_id: str, state: str, result: dict[str, Any], actor: str, now: datetime
    ) -> None:
        key = uuid.UUID(batch_id)
        self._c.execute(
            text(
                "UPDATE batch SET state = :state, confirmed_at = :now, confirmed_by = :actor, "
                "result = :result, original_copy = 'pending', lease_until = NULL, "
                "updated_at = now() WHERE id = :id"
            ).bindparams(bindparam("result", type_=JSONB)),
            {"id": key, "state": state, "now": now, "actor": actor, "result": result},
        )
        # The prepared rows have served their purpose: the result is what stays (BE-11).
        self._c.execute(text("DELETE FROM batch_row WHERE batch_id = :b"), {"b": key})
