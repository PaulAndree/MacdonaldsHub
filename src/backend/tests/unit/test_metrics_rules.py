"""Dashboard rules decided in P-04: claims, recoveries, rate, age and incomplete amounts (RF-15)."""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.metrics import (
    GroupFigures,
    age_days,
    channel_of,
    combine,
    incomplete_message,
    recovery_rate,
)

D = Decimal


def group(**over) -> GroupFigures:  # type: ignore[no-untyped-def]
    base = dict(
        provider="uber eats",
        branch="centro",
        claimed=0,
        claimed_amount=None,
        claimed_incomplete=0,
        recovered=0,
        recovered_amount=None,
        any_incomplete=0,
    )
    return GroupFigures(**{**base, **over})


# --- channels -----------------------------------------------------------------------------------------------


def test_uber_eats_and_just_eat_are_the_email_channel_and_glovo_is_apart() -> None:
    assert channel_of("uber eats") == "email"
    assert channel_of("just eat") == "email"
    assert channel_of("glovo") == "glovo"


# --- sums: only what is known, and absent is never zero ---------------------------------------------------------


def test_known_amounts_are_added_and_the_missing_ones_are_counted() -> None:
    figures = combine(
        [
            group(claimed=2, claimed_amount=D("15.50"), claimed_incomplete=1),
            group(branch="norte", claimed=1, claimed_amount=D("10.00")),
        ]
    )
    assert figures.claimed == 3 and figures.claimed_amount == D("25.50")
    assert figures.incomplete == 1


def test_a_figure_with_no_known_amount_is_absent_not_zero() -> None:
    figures = combine([group(claimed=2, claimed_amount=None, claimed_incomplete=2)])
    assert figures.claimed_amount is None and figures.incomplete == 2
    assert combine([]).claimed_amount is None and combine([]).recovered_amount is None


def test_a_real_zero_is_kept_as_zero() -> None:
    figures = combine(
        [group(claimed=1, claimed_amount=D("0"), recovered=1, recovered_amount=D("0"))]
    )
    assert figures.claimed_amount == D("0") and figures.recovered_amount == D("0")


def test_the_digits_of_the_amounts_are_not_rounded() -> None:
    figures = combine(
        [group(claimed=2, claimed_amount=D("0.1234")), group(claimed=1, claimed_amount=D("0.0001"))]
    )
    assert figures.claimed_amount == D("0.1235")


# --- the rate: recoveries over claims, by number --------------------------------------------------------------------


def test_the_rate_counts_every_claim_of_the_period_pending_and_rejected_included() -> None:
    # 5 claims, 1 resolved, 2 still without result and 2 rejected: 1 / 5
    assert recovery_rate(1, 5, "claim") == "0.2000"


def test_the_rate_has_four_decimals() -> None:
    assert recovery_rate(1, 3, "claim") == "0.3333"
    assert recovery_rate(2, 3, "incident") == "0.6667"
    assert recovery_rate(3, 3, "claim") == "1.0000"
    assert (
        recovery_rate(0, 4, "claim") == "0.0000"
    )  # a real zero: there were claims and none recovered


def test_no_claims_means_no_rate_not_zero() -> None:
    assert recovery_rate(0, 0, "claim") is None


def test_with_the_recovery_date_the_claims_of_the_period_are_not_defined() -> None:
    assert recovery_rate(3, 3, "recovery") is None


# --- age of claims without result --------------------------------------------------------------------------------------


def test_age_is_calendar_days_from_the_claim_date() -> None:
    assert age_days(date(2026, 11, 13), date(2026, 11, 23)) == 10
    assert age_days(date(2026, 11, 21), date(2026, 11, 23)) == 2
    assert age_days(date(2026, 11, 23), date(2026, 11, 23)) == 0


def test_a_claim_dated_in_the_future_has_age_zero_not_negative() -> None:
    assert age_days(date(2026, 11, 25), date(2026, 11, 23)) == 0


# --- warning text -----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (1, "Hay 1 incidencia sin importe: los totales están incompletos."),
        (3, "Hay 3 incidencias sin importe: los totales están incompletos."),
    ],
)
def test_the_incomplete_warning_says_how_many(count: int, text: str) -> None:
    assert incomplete_message(count) == text
