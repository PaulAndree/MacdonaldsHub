"""Dashboard rules decided in P-04 (RF-15). Pure rules, no I/O.

A claim is an incident with a claim date; a recovery is an incident marked Resuelta. The rate is
recoveries divided by claims, by number, and is absent when it cannot be computed. Amounts add up
only what is known: an absent amount is counted as missing and never as zero.
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

Channel = Literal["email", "glovo"]
NO_DATA_MESSAGE = "No hay datos para el periodo seleccionado."


def channel_of(provider: str) -> Channel:
    """Claims by email and manual Glovo claims are always kept apart."""
    return "glovo" if provider == "glovo" else "email"


@dataclass(frozen=True)
class GroupFigures:
    """The figures of one provider and branch, as PostgreSQL aggregated them."""

    provider: str
    branch: str | None
    claimed: int
    claimed_amount: Decimal | None  # None when no claim of the group has an amount
    claimed_incomplete: int  # claims without claim amount
    recovered: int
    recovered_amount: Decimal | None  # None when no recovery has a recorded amount
    any_incomplete: int  # incidents with a missing claim amount or a missing recovered amount


@dataclass(frozen=True)
class Figures:
    claimed: int
    claimed_amount: Decimal | None
    recovered: int
    recovered_amount: Decimal | None
    incomplete: int  # claims without claim amount (the sum is incomplete)
    any_incomplete: int


def _add(values: list[Decimal | None]) -> Decimal | None:
    known = [v for v in values if v is not None]
    return sum(known, Decimal(0)) if known else None


def combine(groups: list[GroupFigures]) -> Figures:
    return Figures(
        claimed=sum(g.claimed for g in groups),
        claimed_amount=_add([g.claimed_amount for g in groups]),
        recovered=sum(g.recovered for g in groups),
        recovered_amount=_add([g.recovered_amount for g in groups]),
        incomplete=sum(g.claimed_incomplete for g in groups),
        any_incomplete=sum(g.any_incomplete for g in groups),
    )


def recovery_rate(recovered: int, claimed: int, date_kind: str) -> str | None:
    """Recoveries over claims with four decimals; absent when there are no claims or when the
    recovery date is the one used (the claims of that period are not defined)."""
    if claimed == 0 or date_kind == "recovery":
        return None
    rate = (Decimal(recovered) / Decimal(claimed)).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    return format(rate, "f")


def age_days(claim_date: date, today: date) -> int:
    """Calendar days since the claim; never negative."""
    return max(0, (today - claim_date).days)


def incomplete_message(count: int) -> str:
    noun = "incidencia sin importe" if count == 1 else "incidencias sin importe"
    return f"Hay {count} {noun}: los totales están incompletos."
