"""When the next attempt may start and who may receive it (RN-05, RN-08, MAIL-01, MAIL-10)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.mail_rules import (
    MIN_INTERVAL_SECONDS,
    can_start,
    next_eligible_at,
    recipient_authorized,
)

T0 = datetime(2026, 11, 23, 10, 0, 0, tzinfo=UTC)


def test_the_interval_is_30_seconds_and_fixed() -> None:
    assert MIN_INTERVAL_SECONDS == 30


# --- the interval ---------------------------------------------------------------------------------------


def test_the_first_attempt_can_start_at_once() -> None:
    assert can_start(paused=False, last_started_at=None, now=T0)


@pytest.mark.parametrize(
    ("seconds", "allowed"),
    [(0, False), (29, False), (29.9, False), (30, True), (31, True), (3600, True)],
)
def test_an_attempt_needs_30_seconds_since_the_start_of_the_previous_one(
    seconds: float, allowed: bool
) -> None:
    assert can_start(False, T0, T0 + timedelta(seconds=seconds)) is allowed


def test_the_interval_counts_from_the_start_not_from_the_end() -> None:
    # A slow attempt that ended after 25 s still leaves only 5 s to wait.
    assert not can_start(False, T0, T0 + timedelta(seconds=29))
    assert can_start(False, T0, T0 + timedelta(seconds=30))


def test_a_paused_queue_never_starts_even_after_the_interval() -> None:
    assert not can_start(True, None, T0)
    assert not can_start(True, T0, T0 + timedelta(hours=1))


def test_the_next_eligible_time_is_30_seconds_after_the_last_start() -> None:
    assert next_eligible_at(False, T0) == T0 + timedelta(seconds=30)
    assert next_eligible_at(False, None) is None  # nothing started yet: it can start now


def test_there_is_no_next_time_while_paused() -> None:
    assert next_eligible_at(True, T0) is None


# --- who may receive it ----------------------------------------------------------------------------------


def test_only_the_configured_test_recipient_is_authorized() -> None:
    assert recipient_authorized("test-recipient@example.test", "test-recipient@example.test")


def test_the_comparison_ignores_letter_case() -> None:
    assert recipient_authorized("Test-Recipient@Example.Test", "test-recipient@example.test")


@pytest.mark.parametrize(
    "stored",
    ["", "uber@real-provider.example", "test-recipient@example.test.evil", "x@example.test"],
)
def test_any_other_recipient_is_not_authorized(stored: str) -> None:
    assert not recipient_authorized(stored, "test-recipient@example.test")


def test_without_a_configured_recipient_nothing_is_authorized() -> None:
    assert not recipient_authorized("test-recipient@example.test", None)
    assert not recipient_authorized("test-recipient@example.test", "")
