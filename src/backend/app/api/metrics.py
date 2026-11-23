"""The dashboard operation of the approved contract (getMetrics)."""

from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, StringConstraints

from app.api.errors import SECURED
from app.api.incidents import IncidentDate, Provider, _real_date_or_422
from app.api.security import require_permission
from app.services.authorization import AuthorizedUser
from app.services.incidents import IncidentFilters
from app.services.metrics import Dashboard, MetricsService

router = APIRouter(tags=["metrics"])

Reader = Annotated[AuthorizedUser, Depends(require_permission("metrics_read"))]
Amount = Annotated[str, StringConstraints(pattern=r"^-?\d+(\.\d+)?$")]
Rate = Annotated[str, StringConstraints(pattern=r"^\d+(\.\d+)?$")]


class CriteriaStatus(BaseModel):
    status: Literal["example", "approved"]
    pendingDecision: str | None


class ChannelMetrics(BaseModel):
    channel: Literal["email", "glovo"]
    claimedCount: int = Field(ge=0)
    claimedAmount: Amount | None
    recoveredCount: int = Field(ge=0)
    recoveredAmount: Amount | None
    incompleteCount: int = Field(ge=0)
    recoveryRate: Rate | None


class BreakdownRow(BaseModel):
    provider: Provider
    branch: str | None
    claimedCount: int = Field(ge=0)
    claimedAmount: Amount | None
    recoveredCount: int = Field(ge=0)
    recoveredAmount: Amount | None
    incompleteCount: int = Field(ge=0)


class PendingClaim(BaseModel):
    incidentId: str
    provider: Provider
    claimDate: IncidentDate
    ageDays: int = Field(ge=0)


class MetricsWarning(BaseModel):
    code: Literal["incomplete_amounts", "no_data"]
    message: str
    count: int = Field(ge=0)


class Metrics(BaseModel):
    environment: Literal["local", "test", "production"]
    dateKind: Literal["incident", "claim", "recovery"]
    criteria: CriteriaStatus
    channels: list[ChannelMetrics]
    breakdown: list[BreakdownRow]
    pendingClaims: list[PendingClaim]
    warnings: list[MetricsWarning]


def metrics_service(request: Request) -> MetricsService:
    state = request.app.state
    if getattr(state, "metrics_service", None) is None:
        from app.adapters.db.metrics import SqlMetricsRepository

        state.metrics_service = MetricsService(SqlMetricsRepository(state.engine))
    service: MetricsService = state.metrics_service
    return service


def _money(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def to_api(dashboard: Dashboard, environment: str) -> Metrics:
    return Metrics.model_validate(
        {
            "environment": environment,
            "dateKind": dashboard.date_kind,
            # The criteria are the ones the administrator decided (P-04).
            "criteria": {"status": "approved", "pendingDecision": None},
            "channels": [
                {
                    "channel": c.channel,
                    "claimedCount": c.figures.claimed,
                    "claimedAmount": _money(c.figures.claimed_amount),
                    "recoveredCount": c.figures.recovered,
                    "recoveredAmount": _money(c.figures.recovered_amount),
                    "incompleteCount": c.figures.incomplete,
                    "recoveryRate": c.recovery_rate,
                }
                for c in dashboard.channels
            ],
            "breakdown": [
                {
                    "provider": b.provider,
                    "branch": b.branch,
                    "claimedCount": b.figures.claimed,
                    "claimedAmount": _money(b.figures.claimed_amount),
                    "recoveredCount": b.figures.recovered,
                    "recoveredAmount": _money(b.figures.recovered_amount),
                    "incompleteCount": b.figures.incomplete,
                }
                for b in dashboard.breakdown
            ],
            "pendingClaims": [
                {
                    "incidentId": p.incident_id,
                    "provider": p.provider,
                    "claimDate": p.claim_date.isoformat(),
                    "ageDays": p.age_days,
                }
                for p in dashboard.pending_claims
            ],
            "warnings": [
                {"code": w.code, "message": w.message, "count": w.count} for w in dashboard.warnings
            ],
        }
    )


@router.get(
    "/api/metrics",
    operation_id="getMetrics",
    response_model=Metrics,
    responses=SECURED,
)
def get_metrics(
    request: Request,
    user: Reader,
    service: Annotated[MetricsService, Depends(metrics_service)],
    dateKind: Annotated[Literal["incident", "claim", "recovery"], Query()] = "claim",
    date_from: Annotated[IncidentDate | None, Query(alias="from")] = None,
    date_to: Annotated[IncidentDate | None, Query(alias="to")] = None,
    provider: Annotated[Provider | None, Query()] = None,
    branch: Annotated[str | None, Query()] = None,
) -> Metrics:
    for value in (date_from, date_to):
        _real_date_or_422(value)
    filters = IncidentFilters(
        provider=provider,
        branch=branch.lower() if branch else None,
        date_kind=dateKind,
        date_from=date_from,
        date_to=date_to,
    )
    return to_api(service.dashboard(filters), request.app.state.settings.app_env)
