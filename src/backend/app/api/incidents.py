"""Incident operations of the approved contract: queries, export, manual claims, results and
corrections, and manual entry. Nothing here sends an email or touches a batch."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.adapters.xlsx.writer import build_incident_export
from app.api.authorized_email import authorized_email
from app.api.errors import CONFLICT, NOT_FOUND, SECURED
from app.api.security import ApiError, require_permission
from app.domain.incident_results import ClaimNotAvailable, NoResultToCorrect, NotClaimed
from app.domain.rows import Fields
from app.services.authorization import AuthorizedUser
from app.services.confirmation import RecipientNotConfigured
from app.services.incidents import (
    HistoryItem,
    IncidentExists,
    IncidentFilters,
    IncidentNotFound,
    IncidentRecord,
    IncidentService,
    UnknownBranch,
)

router = APIRouter(tags=["incidents"])

Reader = Annotated[AuthorizedUser, Depends(require_permission("incidents_read"))]
Writer = Annotated[AuthorizedUser, Depends(require_permission("incidents_write"))]

Provider = Literal["uber eats", "just eat", "glovo"]
Status = Literal[
    "imported_no_email", "pending_send", "claimed", "send_error", "resolved", "rejected"
]
ResultKind = Literal["resolved", "rejected"]
IncidentDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
IncidentTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Amount = Annotated[str, StringConstraints(pattern=r"^-?\d+(\.\d+)?$")]


def _real_date(value: str | None) -> str | None:
    """A calendar date that exists (the pattern alone would accept 2026-02-30)."""
    if value is not None:
        date.fromisoformat(value)
    return value


class IncidentCore(BaseModel):
    provider: Provider
    orderId: str = Field(min_length=1)
    incidentDate: IncidentDate
    incidentTime: IncidentTime | None
    branch: str | None
    claimAmount: Amount | None
    providerCosts: Amount | None
    total: Amount | None
    description: str | None

    _day = field_validator("incidentDate")(_real_date)

    def to_fields(self) -> Fields:
        return Fields(
            provider=self.provider,
            order_id=self.orderId,
            incident_date=date.fromisoformat(self.incidentDate),
            incident_time=datetime.strptime(self.incidentTime, "%H:%M").time()
            if self.incidentTime
            else None,
            branch=self.branch.lower() if self.branch else None,
            claim_amount=Decimal(self.claimAmount) if self.claimAmount is not None else None,
            provider_costs=Decimal(self.providerCosts) if self.providerCosts is not None else None,
            total=Decimal(self.total) if self.total is not None else None,
            description=self.description,
        )


class Incident(IncidentCore):
    id: str
    batchId: str | None
    status: Status
    channel: Literal["email", "glovo"]
    claimDate: IncidentDate | None
    recoveryDate: IncidentDate | None
    recoveredAmount: Amount | None
    result: ResultKind | None


class IncidentPage(BaseModel):
    items: list[Incident]
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    total: int = Field(ge=0)


class HistoryEntry(BaseModel):
    at: datetime
    actor: str
    kind: Literal["imported", "email_result", "claim", "result", "correction"]
    field: Literal["status", "claimDate", "result", "recoveredAmount", "recoveryDate"]
    previousValue: str | None
    newValue: str | None
    reason: str | None


class IncidentDetail(BaseModel):
    incident: Incident
    history: list[HistoryEntry]


class ManualCheckResult(BaseModel):
    outcome: Literal["new", "duplicate", "conflict"]
    existing: IncidentCore | None
    differingFields: list[str]


class ClaimRequest(BaseModel):
    claimDate: IncidentDate
    _day = field_validator("claimDate")(_real_date)


class ResultRequest(BaseModel):
    result: ResultKind
    recoveredAmount: Amount | None
    recoveryDate: IncidentDate | None
    _day = field_validator("recoveryDate")(_real_date)


class CorrectionRequest(ResultRequest):
    reason: str = Field(min_length=1)


class Branch(BaseModel):
    id: str
    name: str
    active: bool


class BranchList(BaseModel):
    items: list[Branch]


def _money(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _core(record: IncidentRecord) -> dict[str, Any]:
    return {
        "provider": record.provider,
        "orderId": record.order_id,
        "incidentDate": record.incident_date.isoformat(),
        "incidentTime": record.incident_time.strftime("%H:%M") if record.incident_time else None,
        "branch": record.branch,
        "claimAmount": _money(record.claim_amount),
        "providerCosts": _money(record.provider_costs),
        "total": _money(record.total),
        "description": record.description,
    }


def to_incident(record: IncidentRecord) -> Incident:
    return Incident(
        **_core(record),
        id=record.id,
        batchId=record.batch_id,
        status=record.status,  # type: ignore[arg-type]
        channel=record.channel,  # type: ignore[arg-type]
        claimDate=record.claim_date.isoformat() if record.claim_date else None,
        recoveryDate=record.recovery_date.isoformat() if record.recovery_date else None,
        recoveredAmount=_money(record.recovered_amount),
        result=record.result,  # type: ignore[arg-type]
    )


def to_history(item: HistoryItem) -> HistoryEntry:
    return HistoryEntry(
        at=item.at,
        actor=item.actor,
        kind=item.kind,  # type: ignore[arg-type]
        field=item.field,  # type: ignore[arg-type]
        previousValue=item.previous,
        newValue=item.new,
        reason=item.reason,
    )


def incident_service(request: Request) -> IncidentService:
    state = request.app.state
    if getattr(state, "incident_service", None) is None:
        from app.adapters.db.unit_of_work import SqlUnitOfWork

        state.incident_service = IncidentService(
            SqlUnitOfWork(state.engine), email=lambda: authorized_email(request)
        )
    service: IncidentService = state.incident_service
    return service


Service = Annotated[IncidentService, Depends(incident_service)]


def not_found() -> ApiError:
    return ApiError(404, {"code": "not_found", "message": "No se encontró el elemento solicitado."})


def filters(
    provider: Annotated[Provider | None, Query()] = None,
    branch: Annotated[str | None, Query()] = None,
    status: Annotated[Status | None, Query()] = None,
    dateKind: Annotated[Literal["incident", "claim", "recovery"], Query()] = "incident",
    date_from: Annotated[IncidentDate | None, Query(alias="from")] = None,
    date_to: Annotated[IncidentDate | None, Query(alias="to")] = None,
) -> IncidentFilters:
    for value in (date_from, date_to):
        _real_date_or_422(value)
    return IncidentFilters(
        provider=provider,
        branch=branch.lower() if branch else None,
        status=status,
        date_kind=dateKind,
        date_from=date_from,
        date_to=date_to,
    )


def _real_date_or_422(value: str | None) -> None:
    try:
        _real_date(value)
    except ValueError:
        raise ApiError(
            422, {"code": "invalid_request", "message": "La fecha no es válida."}
        ) from None


Filters = Annotated[IncidentFilters, Depends(filters)]


@router.get(
    "/api/incidents",
    operation_id="listIncidents",
    response_model=IncidentPage,
    responses=SECURED,
)
def list_incidents(
    user: Reader,
    service: Service,
    selected: Filters,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=200)] = 50,
) -> IncidentPage:
    result = service.search(selected, page, pageSize)
    return IncidentPage(
        items=[to_incident(r) for r in result.items],
        page=result.page,
        pageSize=result.page_size,
        total=result.total,
    )


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/api/incidents/export",
    operation_id="exportIncidents",
    response_class=Response,
    responses={
        200: {
            "description": "The export file.",
            "content": {XLSX: {"schema": {"type": "string", "format": "binary"}}},
        },
        **SECURED,
    },
)
def export_incidents(user: Reader, service: Service, selected: Filters) -> Response:
    content = build_incident_export(service.export(selected))
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="incidencias.xlsx"'},
    )


def _checked(core: IncidentCore, service: IncidentService) -> Fields:
    fields = core.to_fields()
    if fields.branch is not None and fields.branch not in service.branches():
        raise ApiError(
            422,
            {
                "code": "unknown_branch",
                "message": f"La sucursal «{fields.branch}» no es una sucursal conocida.",
            },
        )
    return fields


@router.post(
    "/api/incidents/manual/check",
    operation_id="checkManualIncident",
    response_model=ManualCheckResult,
    responses=SECURED,
)
def check_manual(body: IncidentCore, user: Writer, service: Service) -> ManualCheckResult:
    check = service.check_manual(_checked(body, service))
    return ManualCheckResult(
        outcome=check.outcome,  # type: ignore[arg-type]
        existing=IncidentCore(**_core(check.existing)) if check.existing else None,
        differingFields=check.differing_fields,
    )


@router.post(
    "/api/incidents/manual",
    operation_id="createManualIncident",
    status_code=201,
    response_model=Incident,
    responses={**SECURED, **CONFLICT},
)
def create_manual(body: IncidentCore, user: Writer, service: Service) -> Incident:
    fields = _checked(body, service)
    try:
        return to_incident(service.create_manual(user.identifier, fields))
    except IncidentExists:
        raise ApiError(
            409,
            {
                "code": "incident_exists",
                "message": "Ya existe una incidencia con ese proveedor y ese Order ID.",
            },
        ) from None
    except RecipientNotConfigured:
        raise ApiError(
            409,
            {
                "code": "recipient_not_configured",
                "message": "No hay un destinatario autorizado configurado para los correos.",
            },
        ) from None
    except UnknownBranch:  # pragma: no cover - checked above, kept for a race with the catalog
        raise ApiError(
            422, {"code": "unknown_branch", "message": "Sucursal desconocida."}
        ) from None


@router.get(
    "/api/incidents/{incidentId}",
    operation_id="getIncident",
    response_model=IncidentDetail,
    responses={**SECURED, **NOT_FOUND},
)
def get_incident(incidentId: str, user: Reader, service: Service) -> IncidentDetail:
    try:
        record, history = service.detail(incidentId)
    except IncidentNotFound:
        raise not_found() from None
    return IncidentDetail(incident=to_incident(record), history=[to_history(h) for h in history])


@router.post(
    "/api/incidents/{incidentId}/claim",
    operation_id="claimGlovoIncident",
    response_model=Incident,
    responses={**SECURED, **NOT_FOUND, **CONFLICT},
)
def claim_incident(incidentId: str, body: ClaimRequest, user: Writer, service: Service) -> Incident:
    try:
        return to_incident(service.claim(user.identifier, incidentId, body.claimDate))
    except IncidentNotFound:
        raise not_found() from None
    except ClaimNotAvailable:
        raise ApiError(
            409,
            {
                "code": "claim_not_available",
                "message": (
                    "Esta incidencia no se puede reclamar de forma manual porque tiene un correo "
                    "asociado o ya está reclamada."
                ),
            },
        ) from None


@router.post(
    "/api/incidents/{incidentId}/result",
    operation_id="recordIncidentResult",
    response_model=Incident,
    responses={**SECURED, **NOT_FOUND, **CONFLICT},
)
def record_result(incidentId: str, body: ResultRequest, user: Writer, service: Service) -> Incident:
    try:
        return to_incident(
            service.record_result(
                user.identifier, incidentId, body.result, body.recoveredAmount, body.recoveryDate
            )
        )
    except IncidentNotFound:
        raise not_found() from None
    except NotClaimed:
        raise ApiError(
            409,
            {
                "code": "incident_not_claimed",
                "message": (
                    "Solo se puede registrar el resultado de una incidencia reclamada. Para "
                    "cambiar uno ya registrado use una corrección."
                ),
            },
        ) from None


@router.post(
    "/api/incidents/{incidentId}/corrections",
    operation_id="correctIncidentResult",
    response_model=IncidentDetail,
    responses={**SECURED, **NOT_FOUND, **CONFLICT},
)
def correct_result(
    incidentId: str, body: CorrectionRequest, user: Writer, service: Service
) -> IncidentDetail:
    try:
        record, history = service.correct_result(
            user.identifier,
            incidentId,
            body.result,
            body.recoveredAmount,
            body.recoveryDate,
            body.reason,
        )
    except IncidentNotFound:
        raise not_found() from None
    except NoResultToCorrect:
        raise ApiError(
            409,
            {
                "code": "no_result_to_correct",
                "message": "Esta incidencia todavía no tiene un resultado registrado que corregir.",
            },
        ) from None
    return IncidentDetail(incident=to_incident(record), history=[to_history(h) for h in history])


@router.get(
    "/api/branches",
    operation_id="listBranchOptions",
    response_model=BranchList,
    responses=SECURED,
)
def list_branches(user: Reader, service: Service) -> BranchList:
    names = service.branches()
    return BranchList(items=[Branch(id=n, name=n, active=True) for n in names])
