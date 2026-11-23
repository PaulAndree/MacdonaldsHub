"""Audit use case: builds a valid record and hands it to the log (RNF-05, RF-19)."""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.domain.clock import to_utc, utc_now
from app.services.ports import AuditEntry, AuditLog

OUTCOMES = ("success", "failure")


class Auditor:
    """Every operation records its actor, UTC instant, object and outcome through this class."""

    def __init__(self, log: AuditLog, clock: Callable[[], datetime] = utc_now) -> None:
        self._log = log
        self._clock = clock

    def record(
        self,
        actor: str,
        operation: str,
        object_type: str,
        object_id: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not actor.strip():
            raise ValueError("an audit record needs an actor (a user or system:<task>)")
        if outcome not in OUTCOMES:
            raise ValueError(f"audit outcome must be one of {OUTCOMES}")
        self._log.record(
            AuditEntry(
                actor=actor,
                at=to_utc(self._clock()),  # refuses a naive instant
                operation=operation,
                object_type=object_type,
                object_id=object_id,
                outcome=outcome,
                details=details,
            )
        )
