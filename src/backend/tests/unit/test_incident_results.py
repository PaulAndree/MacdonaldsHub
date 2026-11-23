"""Manual claims, results and corrections (RF-21, RN-15): E-12. No restrictions invented (P-04)."""

from decimal import Decimal

import pytest

from app.domain.incident_results import (
    ClaimNotAvailable,
    IncidentState,
    NoResultToCorrect,
    NotClaimed,
    claim,
    correct_result,
    record_result,
)


def state(status: str = "imported_no_email", **over) -> IncidentState:  # type: ignore[no-untyped-def]
    base = dict(status=status, claim_date=None, recovery_date=None, recovered_amount=None)
    return IncidentState(**{**base, **over})


def fields(changes):  # type: ignore[no-untyped-def]
    return [(c.field, c.previous, c.new) for c in changes]


# --- a manual claim ------------------------------------------------------------------------------------


def test_an_incident_without_email_can_be_claimed_with_a_date() -> None:
    new, changes = claim(state(), "2026-11-21")
    assert (new.status, new.claim_date) == ("claimed", "2026-11-21")
    assert fields(changes) == [
        ("status", "imported_no_email", "claimed"),
        ("claimDate", None, "2026-11-21"),
    ]
    assert {c.kind for c in changes} == {"claim"}


@pytest.mark.parametrize(
    "status", ["pending_send", "send_error", "claimed", "resolved", "rejected"]
)
def test_an_incident_with_an_email_or_already_claimed_cannot_be_claimed_by_hand(
    status: str,
) -> None:
    with pytest.raises(ClaimNotAvailable):
        claim(state(status), "2026-11-21")


# --- recording a result (E-12) -----------------------------------------------------------------------------


def test_a_partial_recovery_is_recorded_as_entered() -> None:
    new, changes = record_result(state("claimed"), "resolved", "12.00", "2026-11-15")
    assert (new.status, new.recovered_amount, new.recovery_date) == (
        "resolved",
        "12.00",
        "2026-11-15",
    )
    assert fields(changes) == [
        ("status", "claimed", "resolved"),
        ("recoveredAmount", None, "12.00"),
        ("recoveryDate", None, "2026-11-15"),
    ]
    assert {c.kind for c in changes} == {"result"}


def test_resolved_does_not_imply_the_whole_amount_was_recovered() -> None:
    new, _ = record_result(state("claimed"), "resolved", "0.01", "2026-11-15")
    assert new.recovered_amount == "0.01"  # nothing is completed from the claimed amount


def test_a_rejection_may_have_no_amount_and_no_date() -> None:
    new, changes = record_result(state("claimed"), "rejected", None, None)
    assert (new.status, new.recovered_amount, new.recovery_date) == ("rejected", None, None)
    assert fields(changes) == [("status", "claimed", "rejected")]


@pytest.mark.parametrize("amount", ["0", "-5", "100000", "0.123456"])
def test_the_recovered_amount_has_no_restriction_until_p04_is_decided(amount: str) -> None:
    new, _ = record_result(state("claimed"), "resolved", amount, "2026-11-15")
    assert new.recovered_amount == amount


@pytest.mark.parametrize(
    "status", ["imported_no_email", "pending_send", "send_error", "resolved", "rejected"]
)
def test_a_result_can_only_be_recorded_for_a_claimed_incident(status: str) -> None:
    with pytest.raises(NotClaimed):
        record_result(state(status), "resolved", "1", "2026-11-15")


# --- audited correction -------------------------------------------------------------------------------------


def resolved() -> IncidentState:
    return state(
        "resolved", claim_date="2026-10-30", recovery_date="2026-11-12", recovered_amount="10.00"
    )


def test_a_correction_keeps_the_previous_value_in_the_history() -> None:
    new, changes = correct_result(resolved(), "resolved", "8.00", "2026-11-12", "Eran 8,00")
    assert new.recovered_amount == "8.00" and new.status == "resolved"
    assert fields(changes) == [("recoveredAmount", "10.00", "8.00")]
    assert {c.kind for c in changes} == {"correction"} and {c.reason for c in changes} == {
        "Eran 8,00"
    }


def test_a_final_result_can_be_corrected_to_another_result() -> None:
    new, changes = correct_result(resolved(), "rejected", None, None, "Se rechazó")
    assert new.status == "rejected" and new.recovered_amount is None and new.recovery_date is None
    assert fields(changes) == [
        ("status", "resolved", "rejected"),
        ("recoveredAmount", "10.00", None),
        ("recoveryDate", "2026-11-12", None),
    ]


def test_amounts_are_compared_by_value_so_the_same_amount_is_no_change() -> None:
    _, changes = correct_result(resolved(), "resolved", "10", "2026-11-12", "igual")
    assert changes == []
    assert Decimal("10") == Decimal("10.00")


@pytest.mark.parametrize("status", ["imported_no_email", "pending_send", "send_error", "claimed"])
def test_only_a_recorded_result_can_be_corrected(status: str) -> None:
    with pytest.raises(NoResultToCorrect):
        correct_result(state(status), "resolved", "1", "2026-11-15", "x")
