"""PostgreSQL aggregation for the dashboard. PostgreSQL does the sums, so amounts stay exact."""

from datetime import date
from typing import Any

from sqlalchemy import Engine, text

from app.adapters.db.incidents import _where
from app.domain.metrics import GroupFigures
from app.services.incidents import IncidentFilters

_GROUPS = (
    "SELECT i.provider, i.branch, "
    "count(*) FILTER (WHERE i.claim_date IS NOT NULL) AS claimed, "
    "sum(i.claim_amount) FILTER (WHERE i.claim_date IS NOT NULL) AS claimed_amount, "
    "count(*) FILTER (WHERE i.claim_date IS NOT NULL AND i.claim_amount IS NULL) "
    "AS claimed_incomplete, "
    "count(*) FILTER (WHERE i.state = 'resolved') AS recovered, "
    "sum(i.recovered_amount) FILTER (WHERE i.state = 'resolved') AS recovered_amount, "
    "count(*) FILTER (WHERE (i.claim_date IS NOT NULL AND i.claim_amount IS NULL) "
    "OR (i.state = 'resolved' AND i.recovered_amount IS NULL)) AS any_incomplete "
    "FROM incident i WHERE {where} GROUP BY i.provider, i.branch ORDER BY i.provider, i.branch"
)
_PENDING = (
    "SELECT i.id::text, i.provider, i.claim_date FROM incident i "
    "WHERE {where} AND i.state = 'claimed' AND i.claim_date IS NOT NULL "
    "ORDER BY i.claim_date, i.id"
)


class SqlMetricsRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def groups(self, filters: IncidentFilters) -> list[GroupFigures]:
        where, params = _where(filters)
        with self._engine.connect() as conn:
            rows = conn.execute(text(_GROUPS.format(where=where)), params)
            return [GroupFigures(**r._mapping) for r in rows]

    def claims_without_result(self, filters: IncidentFilters) -> list[tuple[str, str, date]]:
        where, params = _where(filters)
        with self._engine.connect() as conn:
            rows: Any = conn.execute(text(_PENDING.format(where=where)), params)
            return [(r[0], r[1], r[2]) for r in rows]
