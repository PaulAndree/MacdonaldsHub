"""Incidents after confirmation: queries, manual claims, results, corrections and manual entry.

Every change is one unit of work: the incident, its append-only history and its audit record
commit together. Nothing here reaches the batch or an email (RF-21).
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import date, datetime, time
from decimal import Decimal
from typing import Protocol

from app.domain.classification import differing_fields
from app.domain.clock import utc_now
from app.domain.incident_results import (
    Change,
    IncidentState,
    claim,
    correct_result,
    record_result,
)
from app.domain.rows import Fields
from app.services.audit import Auditor
from app.services.confirmation import AuthorizedEmail, RecipientNotConfigured

EMAIL_PROVIDERS = ("uber eats", "just eat")


class IncidentNotFound(Exception):
    pass


class IncidentExists(Exception):
    """A manual entry whose provider + Order ID already exist: nothing is created."""


class UnknownBranch(Exception):
    def __init__(self, branch: str) -> None:
        super().__init__(branch)
        self.branch = branch


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    batch_id: str | None
    provider: str
    order_id: str
    incident_date: date
    incident_time: time | None
    branch: str | None
    claim_amount: Decimal | None
    provider_costs: Decimal | None
    total: Decimal | None
    description: str | None
    status: str
    claim_date: date | None
    recovery_date: date | None
    recovered_amount: Decimal | None

    @property
    def channel(self) -> str:
        return "glovo" if self.provider == "glovo" else "email"

    @property
    def result(self) -> str | None:
        return self.status if self.status in ("resolved", "rejected") else None

    @property
    def fields(self) -> Fields:
        return Fields(
            provider=self.provider,
            order_id=self.order_id,
            incident_date=self.incident_date,
            incident_time=self.incident_time,
            branch=self.branch,
            claim_amount=self.claim_amount,
            provider_costs=self.provider_costs,
            total=self.total,
            description=self.description,
        )


@dataclass(frozen=True)
class HistoryItem:
    at: datetime
    actor: str
    kind: str
    field: str
    previous: str | None
    new: str | None
    reason: str | None


@dataclass(frozen=True)
class IncidentFilters:
    provider: str | None = None
    branch: str | None = None  # a branch, or "none" for incidents without one
    status: str | None = None
    date_kind: str = "incident"  # incident | claim | recovery
    date_from: str | None = None
    date_to: str | None = None


@dataclass(frozen=True)
class IncidentPage:
    items: list[IncidentRecord]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class ManualCheck:
    outcome: str  # new | duplicate | conflict
    existing: IncidentRecord | None
    differing_fields: list[str]


class IncidentRepository(Protocol):
    def page(self, filters: IncidentFilters, page: int, size: int) -> IncidentPage: ...

    def every(self, filters: IncidentFilters) -> list[IncidentRecord]: ...

    def get(self, incident_id: str) -> IncidentRecord | None: ...

    def lock(self, incident_id: str) -> IncidentRecord | None: ...

    def history(self, incident_id: str) -> list[HistoryItem]: ...

    def find_by_key(self, provider: str, order_id: str) -> IncidentRecord | None: ...

    def save_state(self, incident_id: str, state: IncidentState) -> None: ...

    def add_history(self, incident_id: str, actor: str, changes: list[Change]) -> None: ...

    def insert_manual(self, fields: Fields, actor: str, state: str) -> str | None: ...

    def add_outbox(self, incident_id: str, email: AuthorizedEmail) -> None: ...

    def active_branches(self) -> list[str]: ...


class IncidentTransaction(Protocol):
    @property
    def incidents(self) -> IncidentRepository: ...

    @property
    def audit(self) -> Auditor: ...


class IncidentUnitOfWork(Protocol):
    def __call__(self) -> AbstractContextManager[IncidentTransaction]: ...


def _text(value: Decimal | date | None) -> str | None:
    if value is None:
        return None
    return format(value, "f") if isinstance(value, Decimal) else value.isoformat()


def _state(record: IncidentRecord) -> IncidentState:
    return IncidentState(
        status=record.status,
        claim_date=_text(record.claim_date),
        recovery_date=_text(record.recovery_date),
        recovered_amount=_text(record.recovered_amount),
    )


class IncidentService:
    def __init__(
        self,
        uow: IncidentUnitOfWork,
        email: Callable[[], AuthorizedEmail | None] = lambda: None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._uow = uow
        self._email = email
        self._clock = clock

    # --- reading ---

    def search(self, filters: IncidentFilters, page: int, size: int) -> IncidentPage:
        with self._uow() as tx:
            return tx.incidents.page(filters, page, size)

    def export(self, filters: IncidentFilters) -> list[IncidentRecord]:
        with self._uow() as tx:
            return tx.incidents.every(filters)

    def detail(self, incident_id: str) -> tuple[IncidentRecord, list[HistoryItem]]:
        with self._uow() as tx:
            record = tx.incidents.get(incident_id)
            if record is None:
                raise IncidentNotFound(incident_id)
            return record, tx.incidents.history(incident_id)

    def branches(self) -> list[str]:
        with self._uow() as tx:
            return tx.incidents.active_branches()

    # --- changing an incident ---

    def claim(self, actor: str, incident_id: str, claim_date: str) -> IncidentRecord:
        return self._change(
            actor, incident_id, "incident.claim", lambda s: claim(s, claim_date), None
        )

    def record_result(
        self,
        actor: str,
        incident_id: str,
        result: str,
        recovered_amount: str | None,
        recovery_date: str | None,
    ) -> IncidentRecord:
        return self._change(
            actor,
            incident_id,
            "incident.result",
            lambda s: record_result(s, result, recovered_amount, recovery_date),
            None,
        )

    def correct_result(
        self,
        actor: str,
        incident_id: str,
        result: str,
        recovered_amount: str | None,
        recovery_date: str | None,
        reason: str,
    ) -> tuple[IncidentRecord, list[HistoryItem]]:
        record = self._change(
            actor,
            incident_id,
            "incident.correct",
            lambda s: correct_result(s, result, recovered_amount, recovery_date, reason),
            reason,
        )
        with self._uow() as tx:
            return record, tx.incidents.history(incident_id)

    def _change(
        self,
        actor: str,
        incident_id: str,
        operation: str,
        rule: Callable[[IncidentState], tuple[IncidentState, list[Change]]],
        reason: str | None,
    ) -> IncidentRecord:
        with self._uow() as tx:
            record = tx.incidents.lock(incident_id)  # a change at a time per incident
            if record is None:
                raise IncidentNotFound(incident_id)
            new_state, changes = rule(_state(record))  # raises the rule's own refusal
            if changes:
                tx.incidents.save_state(incident_id, new_state)
                tx.incidents.add_history(incident_id, actor, changes)
            details: dict[str, object] = {"changes": [c.field for c in changes]}
            if reason:
                details["reason"] = reason
            tx.audit.record(actor, operation, "incident", incident_id, "success", details)
            updated = tx.incidents.get(incident_id)
            assert updated is not None
            return updated

    # --- manual entry (RF-22) ---

    def check_manual(self, fields: Fields) -> ManualCheck:
        """Does the key exist? Never creates anything."""
        assert fields.provider is not None and fields.order_id is not None
        with self._uow() as tx:
            existing = tx.incidents.find_by_key(fields.provider, fields.order_id)
        if existing is None:
            return ManualCheck("new", None, [])
        differing = differing_fields(fields, existing.fields)
        return ManualCheck("conflict" if differing else "duplicate", existing, differing)

    def create_manual(self, actor: str, fields: Fields) -> IncidentRecord:
        """Saves a reviewed manual entry. Uber Eats and Just Eat get their email as a pending
        outbox record in the same transaction; Glovo is claimed by hand and gets none (P-12).
        Nothing is sent."""
        assert fields.provider is not None and fields.order_id is not None
        with self._uow() as tx:
            if fields.branch is not None and fields.branch not in tx.incidents.active_branches():
                raise UnknownBranch(fields.branch)
            sends_email = fields.provider in EMAIL_PROVIDERS
            email = self._email() if sends_email else None
            if sends_email and email is None:
                raise RecipientNotConfigured(fields.provider)
            state = "pending_send" if sends_email else "imported_no_email"
            incident_id = tx.incidents.insert_manual(fields, actor, state)
            if incident_id is None:
                raise IncidentExists(fields.order_id)
            if email is not None:
                tx.incidents.add_outbox(incident_id, email)
            tx.audit.record(
                actor,
                "incident.create_manual",
                "incident",
                incident_id,
                "success",
                {"provider": fields.provider, "email": email is not None},
            )
            created = tx.incidents.get(incident_id)
            assert created is not None
            return replace(created)
