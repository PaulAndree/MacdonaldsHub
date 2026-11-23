"""Exclusive classification of the rows of a file (RN-01, RN-02, RN-03, RF-04). Pure rules, no I/O.

Order: invalid rows are errors first. Among valid rows, those with the same key (provider + Order
ID, never the branch) form a group, and the whole group gets one class together with the existing
incident of that key, if any:

- any difference in a relevant field, inside the group or against the existing incident, makes
  every row of the group a conflict (a conflict prevails over a duplicate);
- otherwise a group that has an existing incident, or more than one row, is made of duplicates;
- otherwise the single row is new.

No row of a repeated key is ever picked to be imported.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.rows import Fields, RowResult

RowClass = Literal["new", "duplicate", "conflict", "error"]
Key = tuple[str, str]

EXISTS_SAME = "Ya existe una incidencia con la misma clave y los mismos datos."
EXISTS_DIFFERENT = "Ya existe una incidencia con la misma clave pero con datos distintos."
REPEATED_SAME = (
    "La clave aparece repetida en el archivo con los mismos datos: "
    "se excluyen todas las apariciones."
)
REPEATED_DIFFERENT = (
    "La clave aparece repetida en el archivo con datos distintos: "
    "se excluyen todas las apariciones."
)


@dataclass(frozen=True)
class SourceRow:
    """A row of the file with its validation result."""

    row_number: int
    result: RowResult


@dataclass(frozen=True)
class Existing:
    """An incident that already exists for a key."""

    id: str
    fields: Fields


@dataclass(frozen=True)
class Classified:
    row_number: int
    row_class: RowClass
    reason: str
    existing_id: str | None = None


def relevant(fields: Fields) -> tuple[object, ...]:
    """The fields compared for the same key (RN-02). Amounts compare by decimal value, so 12.5 and
    12.50 are equal, while an absent amount (None) is never equal to zero."""
    return (
        fields.incident_date,
        fields.incident_time,
        fields.branch,
        fields.claim_amount,
        fields.provider_costs,
        fields.total,
        fields.description,
    )


_NAMES = (
    ("incidentDate", "incident_date"),
    ("incidentTime", "incident_time"),
    ("branch", "branch"),
    ("claimAmount", "claim_amount"),
    ("providerCosts", "provider_costs"),
    ("total", "total"),
    ("description", "description"),
)


def differing_fields(row: Fields, stored: Fields) -> list[str]:
    """Names (as the API calls them) of the relevant fields that differ between two versions."""
    return [api for api, attr in _NAMES if getattr(row, attr) != getattr(stored, attr)]


def classify(rows: Sequence[SourceRow], existing: Mapping[Key, Existing]) -> list[Classified]:
    """One class and one reason per row, in file order. `existing` is looked up by key once."""
    groups: dict[Key, list[SourceRow]] = defaultdict(list)
    for row in rows:
        if row.result.valid:
            f = row.result.fields
            assert f.provider is not None and f.order_id is not None
            groups[(f.provider, f.order_id)].append(row)

    verdicts: dict[int, Classified] = {}
    for key, members in groups.items():
        current = existing.get(key)
        distinct = {relevant(m.result.fields) for m in members}
        differs_from_existing = current is not None and any(
            relevant(m.result.fields) != relevant(current.fields) for m in members
        )
        existing_id = current.id if current else None
        for member in members:
            number = member.row_number
            if len(distinct) > 1 or differs_from_existing:
                # With a stored incident the user compares against it; otherwise against the file.
                reason = EXISTS_DIFFERENT if current is not None else REPEATED_DIFFERENT
                verdicts[number] = Classified(number, "conflict", reason, existing_id)
            elif current is not None:
                verdicts[number] = Classified(number, "duplicate", EXISTS_SAME, existing_id)
            elif len(members) > 1:
                verdicts[number] = Classified(number, "duplicate", REPEATED_SAME)
            else:
                verdicts[number] = Classified(number, "new", "")

    out: list[Classified] = []
    for row in rows:
        if row.result.valid:
            out.append(verdicts[row.row_number])
        else:
            out.append(Classified(row.row_number, "error", " ".join(row.result.errors)))
    return out
