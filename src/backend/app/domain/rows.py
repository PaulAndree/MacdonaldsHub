"""Row rules of the XLSX input (RF-06, RN-06, RN-09, RN-10). Pure rules, no I/O.

A reader turns each spreadsheet cell into a `Cell` (it keeps the raw text of numbers, so no digit
is lost to floating point). `read_row` then validates and converts one row. Only the provider and
the branch are lowercased; nothing else is trimmed, aliased or normalized in v1.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Literal

CellKind = Literal["empty", "text", "number", "datetime", "formula"]

PROVIDERS = frozenset({"uber eats", "just eat", "glovo"})

# Header (as written in the file) -> field. Recognized headers only; extra ones are ignored.
HEADERS: dict[str, str] = {
    "Proveedor": "provider",
    "Order ID": "order_id",
    "Fecha y hora": "when",
    "Sucursal": "branch",
    "Importe a reclamar": "claim_amount",
    "Costos de proveedor": "provider_costs",
    "Total": "total",
    "Descripción": "description",
}
MANDATORY_HEADERS = ("Proveedor", "Order ID", "Fecha y hora")

_DATE_TEXT = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?: (\d{2}):(\d{2}))?$")
_AMOUNT_NAMES = {
    "claim_amount": "importe a reclamar",
    "provider_costs": "costos de proveedor",
    "total": "total",
}
_FIELD_NAMES = {
    "provider": "Proveedor",
    "order_id": "Order ID",
    "when": "Fecha y hora",
    "branch": "Sucursal",
    "description": "Descripción",
    "claim_amount": "Importe a reclamar",
    "provider_costs": "Costos de proveedor",
    "total": "Total",
}


@dataclass(frozen=True)
class Cell:
    """One cell as the reader found it.

    `text` holds the text of a text cell or the raw digits of a numeric cell exactly as stored in
    the file. `when` holds a native date or date-time as a naive local (Europe/Madrid) value.
    """

    kind: CellKind
    text: str = ""
    when: datetime | None = None

    def display(self) -> str | None:
        """What the cell says, as text, for showing a row the way the file had it."""
        if self.kind == "empty":
            return None
        if self.kind == "formula":
            return "(fórmula)"
        if self.kind == "datetime" and self.when is not None:
            moment = self.when
            return (
                moment.strftime("%Y-%m-%d")
                if moment.time() == time(0, 0)
                else moment.strftime("%Y-%m-%d %H:%M")
            )
        return self.text


EMPTY = Cell("empty")


def text(value: str) -> Cell:
    return Cell("text", value) if value != "" else EMPTY


@dataclass(frozen=True)
class Fields:
    """The business fields of a row. A field that could not be read is None (never invented)."""

    provider: str | None = None
    order_id: str | None = None
    incident_date: date | None = None
    incident_time: time | None = None  # only when the source had one; never 00:00 by default
    branch: str | None = None
    claim_amount: Decimal | None = None
    provider_costs: Decimal | None = None
    total: Decimal | None = None
    description: str | None = None


@dataclass(frozen=True)
class RowResult:
    fields: Fields
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def missing_mandatory_headers(headers: Iterable[str]) -> list[str]:
    """Mandatory headers absent from the file; the whole file is rejected if any is. Exact match."""
    present = set(headers)
    return [name for name in MANDATORY_HEADERS if name not in present]


def is_blank(cells: Mapping[str, Cell]) -> bool:
    """A row with nothing in any cell is skipped: it is neither an error nor a counted row."""
    return all(cell.kind == "empty" for cell in cells.values())


def read_row(cells: Mapping[str, Cell], known_branches: frozenset[str]) -> RowResult:
    """Validate and convert one row. Every problem found is reported, not only the first."""
    errors: list[str] = []

    def cell(name: str) -> Cell:
        return cells.get(name, EMPTY)

    # A formula is never evaluated and its calculated value is not trusted (P-09).
    for name in _FIELD_NAMES:
        if cell(name).kind == "formula":
            errors.append(
                f"La celda «{_FIELD_NAMES[name]}» contiene una fórmula; no se evalúan fórmulas."
            )

    provider = _provider(cell("provider"), errors)
    order_id = _order_id(cell("order_id"), errors)
    incident_date, incident_time = _incident_when(cell("when"), errors)
    branch = _branch(cell("branch"), known_branches, errors)
    amounts = {name: _amount(name, cell(name), errors) for name in _AMOUNT_NAMES}
    description = _optional_text(cell("description"))

    fields = Fields(
        provider=provider,
        order_id=order_id,
        incident_date=incident_date,
        incident_time=incident_time,
        branch=branch,
        claim_amount=amounts["claim_amount"],
        provider_costs=amounts["provider_costs"],
        total=amounts["total"],
        description=description,
    )
    return RowResult(fields, tuple(errors))


def _is_formula(c: Cell) -> bool:
    return c.kind == "formula"


def _provider(c: Cell, errors: list[str]) -> str | None:
    if _is_formula(c):
        return None
    if c.kind == "empty":
        errors.append("Falta el proveedor.")
        return None
    shown = c.text if c.kind != "datetime" else str(c.when)
    value = shown.lower()
    if c.kind != "text" or value not in PROVIDERS:
        errors.append(f"El proveedor «{shown}» no es uno de los conocidos.")
        return None
    return value


def _order_id(c: Cell, errors: list[str]) -> str | None:
    if _is_formula(c):
        return None
    if c.kind == "empty":
        errors.append("Falta el Order ID.")
        return None
    if c.kind != "text":
        errors.append("El Order ID debe ser texto, no un número.")
        return None
    return c.text  # exactly as received


def _branch(c: Cell, known: frozenset[str], errors: list[str]) -> str | None:
    if c.kind in ("empty", "formula"):
        return None  # an absent branch is valid: "Sin sucursal"
    shown = c.text if c.kind != "datetime" else str(c.when)
    value = shown.lower()
    if c.kind != "text" or value not in known:
        errors.append(f"La sucursal «{shown}» no es una sucursal conocida.")
        return None
    return value


def _amount(name: str, c: Cell, errors: list[str]) -> Decimal | None:
    if c.kind in ("empty", "formula"):
        return None  # absent is not zero
    if c.kind == "number":
        try:
            value = Decimal(c.text)
        except InvalidOperation:
            value = None
        if value is not None and value.is_finite():
            # Scientific notation (1.5E-3) is only how the file wrote it: keep the value.
            return Decimal(format(value, "f"))
    errors.append(f"El {_AMOUNT_NAMES[name]} debe ser numérico.")
    return None


def _optional_text(c: Cell) -> str | None:
    if c.kind in ("empty", "formula"):
        return None
    return c.text if c.kind in ("text", "number") else str(c.when)


def _incident_when(c: Cell, errors: list[str]) -> tuple[date | None, time | None]:
    if _is_formula(c):
        return None, None
    if c.kind == "empty":
        errors.append("Falta la fecha y hora.")
        return None, None
    if c.kind == "datetime" and c.when is not None:
        # Excel cannot tell "midnight" from "no time", so a native midnight is a date only.
        moment = c.when.replace(second=0, microsecond=0)
        return moment.date(), (None if moment.time() == time(0, 0) else moment.time())
    if c.kind == "text":
        match = _DATE_TEXT.match(c.text)
        if match:
            year, month, day, hour, minute = match.groups()
            try:
                day_value = date(int(year), int(month), int(day))
                clock = None if hour is None else time(int(hour), int(minute))
            except ValueError:
                pass
            else:
                return day_value, clock  # an explicit 00:00 text keeps its time
    shown = c.text if c.kind in ("text", "number") else str(c.when)
    errors.append(f"La fecha y hora «{shown}» no tiene el formato YYYY-MM-DD ni YYYY-MM-DD HH:MM.")
    return None, None
