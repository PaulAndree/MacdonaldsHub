"""PostgreSQL side of incidents. Runs inside the caller's transaction."""

import uuid
from typing import Any

from sqlalchemy import Connection, text

from app.domain.incident_results import Change, IncidentState
from app.domain.rows import Fields
from app.services.incidents import HistoryItem, IncidentFilters, IncidentPage, IncidentRecord

_COLUMNS = (
    "i.id::text AS id, i.batch_id::text AS batch_id, i.provider, i.order_id, i.incident_date, "
    "i.incident_time, i.branch, i.claim_amount, i.provider_costs, i.total, i.description, "
    "i.state AS status, i.claim_date, i.recovery_date, i.recovered_amount"
)
# Which column the date range applies to. Never taken from the request text.
_DATE_COLUMN = {
    "incident": "i.incident_date",
    "claim": "i.claim_date",
    "recovery": "i.recovery_date",
}


def _record(row: Any) -> IncidentRecord:
    return IncidentRecord(**row._mapping)


def _where(filters: IncidentFilters) -> tuple[str, dict[str, Any]]:
    column = _DATE_COLUMN[filters.date_kind]
    clauses = [
        "(CAST(:provider AS text) IS NULL OR i.provider = :provider)",
        "(CAST(:branch AS text) IS NULL OR (:branch = 'none' AND i.branch IS NULL) "
        "OR i.branch = :branch)",
        "(CAST(:status AS text) IS NULL OR i.state = :status)",
        f"(CAST(:from AS date) IS NULL OR {column} >= CAST(:from AS date))",
        f"(CAST(:to AS date) IS NULL OR {column} <= CAST(:to AS date))",
    ]
    params = {
        "provider": filters.provider,
        "branch": filters.branch,
        "status": filters.status,
        "from": filters.date_from,
        "to": filters.date_to,
    }
    return " AND ".join(clauses), params


_ORDER = "ORDER BY i.incident_date DESC, i.created_at DESC, i.id"


class SqlIncidents:
    def __init__(self, connection: Connection) -> None:
        self._c = connection

    def page(self, filters: IncidentFilters, page: int, size: int) -> IncidentPage:
        where, params = _where(filters)
        total = self._c.execute(
            text(f"SELECT count(*) FROM incident i WHERE {where}"), params
        ).scalar()
        rows = self._c.execute(
            text(
                f"SELECT {_COLUMNS} FROM incident i WHERE {where} {_ORDER} "
                "LIMIT :limit OFFSET :offset"
            ),
            {**params, "limit": size, "offset": (page - 1) * size},
        )
        return IncidentPage([_record(r) for r in rows], page, size, int(total or 0))

    def every(self, filters: IncidentFilters) -> list[IncidentRecord]:
        where, params = _where(filters)
        rows = self._c.execute(
            text(f"SELECT {_COLUMNS} FROM incident i WHERE {where} {_ORDER}"), params
        )
        return [_record(r) for r in rows]

    def get(self, incident_id: str) -> IncidentRecord | None:
        key = _uuid(incident_id)
        if key is None:
            return None
        row = self._c.execute(
            text(f"SELECT {_COLUMNS} FROM incident i WHERE i.id = :id"), {"id": key}
        ).first()
        return _record(row) if row else None

    def lock(self, incident_id: str) -> IncidentRecord | None:
        key = _uuid(incident_id)
        if key is None:
            return None
        row = self._c.execute(
            text(f"SELECT {_COLUMNS} FROM incident i WHERE i.id = :id FOR UPDATE OF i"), {"id": key}
        ).first()
        return _record(row) if row else None

    def history(self, incident_id: str) -> list[HistoryItem]:
        rows = self._c.execute(
            text(
                "SELECT at, actor, kind, field, previous, new, reason FROM incident_history "
                "WHERE incident_id = :id ORDER BY at, id"
            ),
            {"id": uuid.UUID(incident_id)},
        )
        return [HistoryItem(**r._mapping) for r in rows]

    def find_by_key(self, provider: str, order_id: str) -> IncidentRecord | None:
        row = self._c.execute(
            text(f"SELECT {_COLUMNS} FROM incident i WHERE i.provider = :p AND i.order_id = :o"),
            {"p": provider, "o": order_id},
        ).first()
        return _record(row) if row else None

    def save_state(self, incident_id: str, state: IncidentState) -> None:
        self._c.execute(
            text(
                "UPDATE incident SET state = :status, claim_date = CAST(:claim AS date), "
                "recovery_date = CAST(:recovery AS date), "
                "recovered_amount = CAST(:amount AS numeric) WHERE id = :id"
            ),
            {
                "id": uuid.UUID(incident_id),
                "status": state.status,
                "claim": state.claim_date,
                "recovery": state.recovery_date,
                "amount": state.recovered_amount,
            },
        )

    def add_history(self, incident_id: str, actor: str, changes: list[Change]) -> None:
        for change in changes:
            self._c.execute(
                text(
                    "INSERT INTO incident_history (incident_id, actor, kind, field, previous, "
                    "new, reason) VALUES (:i, :actor, :kind, :field, :prev, :new, :reason)"
                ),
                {
                    "i": uuid.UUID(incident_id),
                    "actor": actor,
                    "kind": change.kind,
                    "field": change.field,
                    "prev": change.previous,
                    "new": change.new,
                    "reason": change.reason,
                },
            )

    def insert_manual(self, fields: Fields, actor: str) -> str | None:
        found = self._c.execute(
            text(
                "INSERT INTO incident (provider, order_id, incident_date, incident_time, branch, "
                "claim_amount, provider_costs, total, description, state, source, created_by) "
                "VALUES (:provider, :order_id, :date, :time, :branch, :claim, :costs, :total, "
                ":description, 'imported_no_email', 'manual', :actor) "
                "ON CONFLICT (provider, order_id) DO NOTHING RETURNING id"
            ),
            {
                "provider": fields.provider,
                "order_id": fields.order_id,
                "date": fields.incident_date,
                "time": fields.incident_time,
                "branch": fields.branch,
                "claim": fields.claim_amount,
                "costs": fields.provider_costs,
                "total": fields.total,
                "description": fields.description,
                "actor": actor,
            },
        ).scalar()
        if found is None:
            return None
        self._c.execute(
            text(
                "INSERT INTO incident_history (incident_id, actor, kind, field, new) "
                "VALUES (:i, :actor, 'imported', 'status', 'imported_no_email')"
            ),
            {"i": found, "actor": actor},
        )
        return str(found)

    def active_branches(self) -> list[str]:
        return [
            r[0]
            for r in self._c.execute(text("SELECT name FROM branch WHERE active ORDER BY name"))
        ]


def _uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None
