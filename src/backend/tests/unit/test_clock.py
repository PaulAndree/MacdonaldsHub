from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domain.clock import MADRID, to_madrid, to_utc, utc_now


def test_utc_now_is_timezone_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        to_utc(datetime(2026, 1, 1, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        to_madrid(datetime(2026, 1, 1, 12, 0))


def test_to_utc_normalises_other_offsets() -> None:
    dt = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=5)))
    assert to_utc(dt) == datetime(2026, 1, 1, 7, 0, tzinfo=UTC)
    assert to_utc(dt).tzinfo is UTC


def test_madrid_winter_is_utc_plus_1_and_summer_plus_2() -> None:
    winter = to_madrid(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
    summer = to_madrid(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    assert winter.hour == 13 and winter.utcoffset() == timedelta(hours=1)
    assert summer.hour == 14 and summer.utcoffset() == timedelta(hours=2)


def test_presentation_across_spring_forward() -> None:
    # 2026-03-29: clocks go 02:00 -> 03:00 in Madrid (01:00 UTC).
    before = to_madrid(datetime(2026, 3, 29, 0, 59, tzinfo=UTC))
    after = to_madrid(datetime(2026, 3, 29, 1, 0, tzinfo=UTC))
    assert (before.hour, before.minute, before.utcoffset()) == (1, 59, timedelta(hours=1))
    assert (after.hour, after.minute, after.utcoffset()) == (3, 0, timedelta(hours=2))


def test_presentation_across_fall_back() -> None:
    # 2026-10-25: clocks go 03:00 -> 02:00 in Madrid (01:00 UTC). 02:30 occurs twice.
    first = to_madrid(datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
    second = to_madrid(datetime(2026, 10, 25, 1, 30, tzinfo=UTC))
    assert (first.hour, first.minute, first.utcoffset()) == (2, 30, timedelta(hours=2))
    assert (second.hour, second.minute, second.utcoffset()) == (2, 30, timedelta(hours=1))


def test_round_trip_keeps_the_instant() -> None:
    original = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
    assert to_utc(to_madrid(original)) == original
    assert str(MADRID) == "Europe/Madrid"
