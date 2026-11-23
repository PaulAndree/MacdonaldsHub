"""Reads the staging of a prepared batch for the preview."""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, text

from app.domain.classification import differing_fields
from app.domain.rows import Fields
from app.services.preview import PreviewRow, RowsPage

_ROWS = text(
    "SELECT r.row_number, r.class, r.reason, r.provider, r.order_id, r.incident_date, "
    "r.incident_time, r.branch, r.claim_amount, r.provider_costs, r.total, r.description, r.raw, "
    "e.provider AS e_provider, e.order_id AS e_order_id, e.incident_date AS e_date, "
    "e.incident_time AS e_time, e.branch AS e_branch, e.claim_amount AS e_claim, "
    "e.provider_costs AS e_costs, e.total AS e_total, e.description AS e_description, "
    "(SELECT coalesce(array_agg(o.row_number ORDER BY o.row_number), ARRAY[]::int[]) "
    " FROM batch_row o WHERE o.batch_id = r.batch_id AND o.class <> 'error' "
    " AND r.class <> 'error' AND o.provider = r.provider AND o.order_id = r.order_id "
    " AND o.row_number <> r.row_number) AS repeated "
    "FROM batch_row r LEFT JOIN incident e ON e.id = r.existing_incident_id "
    "WHERE r.batch_id = :b AND (CAST(:cls AS text) IS NULL OR r.class = :cls) "
    "AND (NOT CAST(:only_excluded AS boolean) OR r.class <> 'new') "
    "ORDER BY r.row_number LIMIT :limit OFFSET :offset"
)


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _clock(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


def _amount(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _fields(row: Any) -> dict[str, str | None]:
    """The row as text. A valid row is normalized; an invalid one shows what the file said."""
    if row.class_ != "error":
        return {
            "provider": row.provider,
            "orderId": row.order_id,
            "incidentDate": _day(row.incident_date),
            "incidentTime": _clock(row.incident_time),
            "branch": row.branch,
            "claimAmount": _amount(row.claim_amount),
            "providerCosts": _amount(row.provider_costs),
            "total": _amount(row.total),
            "description": row.description,
        }
    raw = row.raw or {}

    def lower(value: str | None) -> str | None:
        return value.lower() if value is not None else None

    return {
        "provider": lower(raw.get("provider")),
        "orderId": raw.get("order_id"),
        "incidentDate": raw.get("when"),
        "incidentTime": None,
        "branch": lower(raw.get("branch")),
        "claimAmount": raw.get("claim_amount"),
        "providerCosts": raw.get("provider_costs"),
        "total": raw.get("total"),
        "description": raw.get("description"),
    }


class SqlPreviewRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def rows_page(
        self, batch_id: str, row_class: str | None, page: int, page_size: int
    ) -> RowsPage:
        key = uuid.UUID(batch_id)
        with self._engine.connect() as conn:
            totals = {"new": 0, "duplicate": 0, "conflict": 0, "error": 0}
            for name, count in conn.execute(
                text("SELECT class, count(*) FROM batch_row WHERE batch_id = :b GROUP BY class"),
                {"b": key},
            ):
                totals[name] = count
            total = totals[row_class] if row_class else sum(totals.values())
            rows = conn.execute(
                _ROWS,
                {
                    "b": key,
                    "cls": row_class,
                    "only_excluded": False,
                    "limit": page_size,
                    "offset": (page - 1) * page_size,
                },
            ).mappings()
            items = [self._item(dict(r)) for r in rows]
        return RowsPage(items, page, page_size, total, totals)

    def excluded_rows(self, batch_id: str) -> list[PreviewRow]:
        """All rows that are not new, in file order (no paging: the report holds every one)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                _ROWS,
                {
                    "b": uuid.UUID(batch_id),
                    "cls": None,
                    "only_excluded": True,
                    "limit": 1_000_000,
                    "offset": 0,
                },
            ).mappings()
            return [self._item(dict(r)) for r in rows]

    @staticmethod
    def _item(r: dict[str, Any]) -> PreviewRow:
        class _R:  # attribute access for the helpers
            pass

        view = _R()
        view.__dict__.update(r, class_=r["class"])
        existing = None
        differing: list[str] = []
        if r["class"] == "conflict" and r["e_order_id"] is not None:
            stored = Fields(
                provider=r["e_provider"],
                order_id=r["e_order_id"],
                incident_date=r["e_date"],
                incident_time=r["e_time"],
                branch=r["e_branch"],
                claim_amount=r["e_claim"],
                provider_costs=r["e_costs"],
                total=r["e_total"],
                description=r["e_description"],
            )
            here = Fields(
                incident_date=r["incident_date"],
                incident_time=r["incident_time"],
                branch=r["branch"],
                claim_amount=r["claim_amount"],
                provider_costs=r["provider_costs"],
                total=r["total"],
                description=r["description"],
            )
            existing = {
                "provider": stored.provider,
                "orderId": stored.order_id,
                "incidentDate": _day(stored.incident_date),
                "incidentTime": _clock(stored.incident_time),
                "branch": stored.branch,
                "claimAmount": _amount(stored.claim_amount),
                "providerCosts": _amount(stored.provider_costs),
                "total": _amount(stored.total),
                "description": stored.description,
            }
            differing = differing_fields(here, stored)
        return PreviewRow(
            row_number=r["row_number"],
            row_class=r["class"],
            reason=r["reason"] or None,
            fields=_fields(view),
            existing=existing,
            differing_fields=differing,
            repeated_in_file=list(r["repeated"] or []),
        )
