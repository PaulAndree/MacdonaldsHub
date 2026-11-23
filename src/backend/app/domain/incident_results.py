"""Manual claims, results and corrections of an incident (RF-21, RN-15). Pure rules, no I/O.

Nothing here limits the recovered amount (P-04) or records the claim channel (P-11). A change never
touches the batch or any email: it only moves the incident and adds to its history.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Literal

ChangeKind = Literal["claim", "result", "correction"]
Field = Literal["status", "claimDate", "recoveredAmount", "recoveryDate"]


class ClaimNotAvailable(Exception):
    """Only an incident without email that has not been claimed can be claimed by hand."""


class NotClaimed(Exception):
    """A result is recorded for a claimed incident; a recorded one is changed by a correction."""


class NoResultToCorrect(Exception):
    """There is no recorded result to correct yet."""


@dataclass(frozen=True)
class IncidentState:
    status: str
    claim_date: str | None  # YYYY-MM-DD
    recovery_date: str | None
    recovered_amount: str | None  # a decimal string, kept as entered


@dataclass(frozen=True)
class Change:
    """One value that changed: what the append-only history records."""

    kind: ChangeKind
    field: Field
    previous: str | None
    new: str | None
    reason: str | None = None


def claim(state: IncidentState, claim_date: str) -> tuple[IncidentState, list[Change]]:
    if state.status != "imported_no_email":
        raise ClaimNotAvailable(state.status)
    new = replace(state, status="claimed", claim_date=claim_date)
    return new, [
        Change("claim", "status", state.status, "claimed"),
        Change("claim", "claimDate", state.claim_date, claim_date),
    ]


def record_result(
    state: IncidentState, result: str, recovered_amount: str | None, recovery_date: str | None
) -> tuple[IncidentState, list[Change]]:
    if state.status != "claimed":
        raise NotClaimed(state.status)
    new = replace(
        state, status=result, recovered_amount=recovered_amount, recovery_date=recovery_date
    )
    changes = [Change("result", "status", state.status, result)]
    if recovered_amount is not None:
        changes.append(
            Change("result", "recoveredAmount", state.recovered_amount, recovered_amount)
        )
    if recovery_date is not None:
        changes.append(Change("result", "recoveryDate", state.recovery_date, recovery_date))
    return new, changes


def _same_amount(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return Decimal(a) == Decimal(b)
    except InvalidOperation:  # pragma: no cover - amounts are validated at the boundary
        return a == b


def correct_result(
    state: IncidentState,
    result: str,
    recovered_amount: str | None,
    recovery_date: str | None,
    reason: str,
) -> tuple[IncidentState, list[Change]]:
    if state.status not in ("resolved", "rejected"):
        raise NoResultToCorrect(state.status)
    changes: list[Change] = []
    amount_changed = not _same_amount(recovered_amount, state.recovered_amount)
    if result != state.status:
        changes.append(Change("correction", "status", state.status, result, reason))
    if amount_changed:
        changes.append(
            Change(
                "correction", "recoveredAmount", state.recovered_amount, recovered_amount, reason
            )
        )
    if recovery_date != state.recovery_date:
        changes.append(
            Change("correction", "recoveryDate", state.recovery_date, recovery_date, reason)
        )
    new = IncidentState(
        status=result,
        claim_date=state.claim_date,
        recovery_date=recovery_date,
        # An amount equal by value keeps the digits it already had: only a real change rewrites it.
        recovered_amount=recovered_amount if amount_changed else state.recovered_amount,
    )
    return new, changes
