"""The dashboard: claims, recoveries, rate, pending claims and warnings (RF-15, P-04).

All the arithmetic is the pure rules of `app.domain.metrics`; PostgreSQL aggregates by provider
and branch, with no separate analytical store.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.domain.clock import to_madrid, utc_now
from app.domain.metrics import (
    NO_DATA_MESSAGE,
    Channel,
    Figures,
    GroupFigures,
    age_days,
    channel_of,
    combine,
    incomplete_message,
    recovery_rate,
)
from app.services.incidents import IncidentFilters


@dataclass(frozen=True)
class PendingClaimItem:
    incident_id: str
    provider: str
    claim_date: date
    age_days: int


@dataclass(frozen=True)
class ChannelFigures:
    channel: Channel
    figures: Figures
    recovery_rate: str | None


@dataclass(frozen=True)
class BreakdownItem:
    provider: str
    branch: str | None
    figures: Figures


@dataclass(frozen=True)
class Warning:
    code: str
    message: str
    count: int


@dataclass(frozen=True)
class Dashboard:
    date_kind: str
    channels: list[ChannelFigures]
    breakdown: list[BreakdownItem]
    pending_claims: list[PendingClaimItem]
    warnings: list[Warning]


class MetricsRepository(Protocol):
    def groups(self, filters: IncidentFilters) -> list[GroupFigures]: ...

    def claims_without_result(self, filters: IncidentFilters) -> list[tuple[str, str, date]]: ...


class MetricsService:
    def __init__(
        self, repository: MetricsRepository, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self._repository = repository
        self._clock = clock

    def dashboard(self, filters: IncidentFilters) -> Dashboard:
        groups = self._repository.groups(filters)
        if not groups:
            return Dashboard(
                filters.date_kind, [], [], [], [Warning("no_data", NO_DATA_MESSAGE, 0)]
            )
        channels = []
        for channel in ("email", "glovo"):
            members = [g for g in groups if channel_of(g.provider) == channel]
            figures = combine(members)
            channels.append(
                ChannelFigures(
                    channel,
                    figures,
                    recovery_rate(figures.recovered, figures.claimed, filters.date_kind),
                )
            )
        breakdown = [
            BreakdownItem(g.provider, g.branch, combine([g]))
            for g in groups
            if g.claimed > 0 or g.recovered > 0
        ]
        today = to_madrid(self._clock()).date()
        pending = [
            PendingClaimItem(incident_id, provider, claim_date, age_days(claim_date, today))
            for incident_id, provider, claim_date in self._repository.claims_without_result(filters)
        ]
        incomplete = combine(groups).any_incomplete
        warnings = (
            [Warning("incomplete_amounts", incomplete_message(incomplete), incomplete)]
            if incomplete
            else []
        )
        return Dashboard(filters.date_kind, channels, breakdown, pending, warnings)
