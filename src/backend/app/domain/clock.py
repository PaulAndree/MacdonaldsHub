"""Time rules (RNF-13): events stored in UTC, presented in Europe/Madrid.

Only aware datetimes are accepted; an incident time of day is never invented here.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")


def utc_now() -> datetime:
    return datetime.now(UTC)


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


def to_utc(value: datetime) -> datetime:
    return _require_aware(value).astimezone(UTC)


def to_madrid(value: datetime) -> datetime:
    return _require_aware(value).astimezone(MADRID)
