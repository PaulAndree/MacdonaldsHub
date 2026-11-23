"""Batch operations of the approved contract: registering a batch, its upload and its state."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.adapters.xlsx.writer import build_excluded_report
from app.api.errors import CONFLICT, NOT_FOUND, SECURED, UNPROCESSABLE
from app.api.security import ApiError, require_permission
from app.domain import email_template
from app.services.authorization import AuthorizedUser
from app.services.batches import (
    BatchNotFound,
    BatchRecord,
    BatchService,
    UnconfirmedBatchExists,
    UploadNotFound,
)
from app.services.confirmation import (
    AuthorizedEmail,
    BatchNotConfirmable,
    ConfirmationService,
    RecipientNotConfigured,
    ReviewedVersionMismatch,
)
from app.services.ports import UploadGrant
from app.services.preview import PreviewRow, PreviewService, RowsPage

router = APIRouter(tags=["batches"])

Importer = Annotated[AuthorizedUser, Depends(require_permission("import"))]
Confirmer = Annotated[AuthorizedUser, Depends(require_permission("confirm"))]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
BatchState = Literal[
    "uploaded", "processing", "in_review", "rejected", "discarded", "confirmed", "completed"
]


class Rejection(BaseModel):
    reason: Literal["missing_required_header", "multiple_worksheets", "corrupt_or_protected_file"]
    detail: str | None


class IdenticalFileNotice(BaseModel):
    confirmedBatchId: str
    confirmedAt: datetime


class ClassTotals(BaseModel):
    new: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    conflict: int = Field(ge=0)
    error: int = Field(ge=0)


class BatchSummary(BaseModel):
    totals: ClassTotals
    incidentsToCreate: int = Field(ge=0)
    emailsToGenerate: int = Field(ge=0)
    withoutEmail: int = Field(ge=0)


class Batch(BaseModel):
    id: str
    state: BatchState
    fileName: str
    createdAt: datetime
    reviewedVersion: Sha256 | None
    rejection: Rejection | None
    identicalFile: IdenticalFileNotice | None
    summary: BatchSummary | None


class UploadGrantOut(BaseModel):
    url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expiresAt: datetime


class BatchUpload(BaseModel):
    batch: Batch
    upload: UploadGrantOut


class CreateBatchRequest(BaseModel):
    fileName: str = Field(min_length=1)
    sizeBytes: int = Field(ge=0)


Provider = Literal["uber eats", "just eat", "glovo"]
RowClass = Literal["new", "duplicate", "conflict", "error"]
IncidentDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
IncidentTime = Annotated[str, StringConstraints(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Amount = Annotated[str, StringConstraints(pattern=r"^-?\d+(\.\d+)?$")]


class RowFields(BaseModel):
    """The values of a row as the file had them, kept as text so nothing is rounded or repaired."""

    provider: str | None
    orderId: str | None
    incidentDate: str | None
    incidentTime: str | None
    branch: str | None
    claimAmount: str | None
    providerCosts: str | None
    total: str | None
    description: str | None


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


class Comparison(BaseModel):
    existing: IncidentCore
    differingFields: list[str]


class Row(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rowNumber: int = Field(ge=1)
    row_class: RowClass = Field(alias="class")
    reason: str | None
    fields: RowFields
    comparison: Comparison | None
    repeatedInFile: list[int]


class RowPage(BaseModel):
    items: list[Row]
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    total: int = Field(ge=0)
    totalsByClass: ClassTotals


def preview_service(request: Request) -> PreviewService:
    state = request.app.state
    if getattr(state, "preview_service", None) is None:
        from app.adapters.db.preview import SqlPreviewRepository
        from app.adapters.db.unit_of_work import SqlUnitOfWork

        state.preview_service = PreviewService(
            SqlUnitOfWork(state.engine), SqlPreviewRepository(state.engine)
        )
    service: PreviewService = state.preview_service
    return service


def _comparison(row: PreviewRow) -> Comparison | None:
    if not row.existing:
        return None
    return Comparison(existing=IncidentCore(**row.existing), differingFields=row.differing_fields)


def page_to_api(page: RowsPage) -> RowPage:
    items = [
        Row.model_validate(
            {
                "rowNumber": r.row_number,
                "class": r.row_class,
                "reason": r.reason,
                "fields": r.fields,
                "comparison": _comparison(r),
                "repeatedInFile": r.repeated_in_file,
            }
        )
        for r in page.items
    ]
    return RowPage(
        items=items,
        page=page.page,
        pageSize=page.page_size,
        total=page.total,
        totalsByClass=ClassTotals(**page.totals_by_class),
    )


def batch_service(request: Request) -> BatchService:
    """Built on first use, so the application can start (and describe itself) without storage."""
    state = request.app.state
    if getattr(state, "batch_service", None) is None:
        from app.adapters.db.unit_of_work import SqlUnitOfWork

        state.batch_service = BatchService(SqlUnitOfWork(state.engine), state.container.storage())
    service: BatchService = state.batch_service
    return service


def to_api(record: BatchRecord) -> Batch:
    in_review_or_later = record.state in ("in_review", "confirmed", "completed")
    return Batch(
        id=record.id,
        state=record.state,  # type: ignore[arg-type]
        fileName=record.file_name,
        createdAt=record.created_at,
        reviewedVersion=record.sha256 if in_review_or_later else None,
        rejection=(
            Rejection(reason=record.rejection_reason, detail=record.rejection_detail)  # type: ignore[arg-type]
            if record.state == "rejected" and record.rejection_reason
            else None
        ),
        identicalFile=(
            IdenticalFileNotice(
                confirmedBatchId=record.identical_batch_id,
                confirmedAt=record.identical_confirmed_at,
            )
            if record.identical_batch_id and record.identical_confirmed_at
            else None
        ),
        summary=(
            BatchSummary(
                totals=ClassTotals(
                    new=record.summary.new,
                    duplicate=record.summary.duplicate,
                    conflict=record.summary.conflict,
                    error=record.summary.error,
                ),
                incidentsToCreate=record.summary.new,
                emailsToGenerate=record.summary.emails_to_generate,
                withoutEmail=record.summary.without_email,
            )
            if record.summary
            else None
        ),
    )


def grant_to_api(grant: UploadGrant) -> UploadGrantOut:
    return UploadGrantOut(
        url=grant.url, method="PUT", headers=grant.headers, expiresAt=grant.expires_at
    )


def not_found(code: str = "not_found") -> ApiError:
    return ApiError(404, {"code": code, "message": "No se encontró el elemento solicitado."})


@router.post(
    "/api/batches",
    operation_id="createBatch",
    status_code=201,
    response_model=BatchUpload,
    responses={**SECURED, **CONFLICT},
)
def create_batch(
    body: CreateBatchRequest,
    user: Importer,
    service: Annotated[BatchService, Depends(batch_service)],
) -> BatchUpload:
    try:
        record, grant = service.create(user.identifier, body.fileName, body.sizeBytes)
    except UnconfirmedBatchExists as exc:
        raise ApiError(
            409,
            {
                "code": "unconfirmed_batch_exists",
                "message": (
                    "Ya tiene un lote sin confirmar. Confírmelo o cancélelo antes de subir otro "
                    "archivo."
                ),
                "details": {"batchId": exc.batch_id},
            },
        ) from None
    return BatchUpload(batch=to_api(record), upload=grant_to_api(grant))


@router.post(
    "/api/batches/{batchId}/uploaded",
    operation_id="completeUpload",
    status_code=202,
    response_model=Batch,
    responses={**SECURED, **NOT_FOUND},
)
def complete_upload(
    batchId: str, user: Importer, service: Annotated[BatchService, Depends(batch_service)]
) -> Batch:
    try:
        return to_api(service.complete_upload(user.identifier, batchId))
    except BatchNotFound:
        raise not_found() from None
    except UploadNotFound:
        raise ApiError(
            404,
            {
                "code": "upload_not_found",
                "message": (
                    "El archivo no llegó a almacenarse correctamente. Puede volver a seleccionarlo."
                ),
            },
        ) from None


@router.get(
    "/api/batches/{batchId}",
    operation_id="getBatch",
    response_model=Batch,
    responses={**SECURED, **NOT_FOUND},
)
def get_batch(
    batchId: str, user: Importer, service: Annotated[BatchService, Depends(batch_service)]
) -> Batch:
    try:
        return to_api(service.get(user.identifier, batchId))
    except BatchNotFound:
        raise not_found() from None


@router.get(
    "/api/batches/{batchId}/rows",
    operation_id="listBatchRows",
    response_model=RowPage,
    responses={**SECURED, **NOT_FOUND},
)
def list_batch_rows(
    batchId: str,
    user: Importer,
    service: Annotated[PreviewService, Depends(preview_service)],
    row_class: Annotated[RowClass | None, Query(alias="class")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=200)] = 50,
) -> RowPage:
    try:
        return page_to_api(service.rows(user.identifier, batchId, row_class, page, pageSize))
    except BatchNotFound:
        raise not_found() from None


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/api/batches/{batchId}/excluded-report",
    operation_id="downloadExcludedReport",
    response_class=Response,
    responses={
        200: {
            "description": "The report file.",
            "content": {XLSX: {"schema": {"type": "string", "format": "binary"}}},
        },
        **SECURED,
        **NOT_FOUND,
    },
)
def download_excluded_report(
    batchId: str,
    user: Importer,
    service: Annotated[PreviewService, Depends(preview_service)],
) -> Response:
    try:
        content = build_excluded_report(service.excluded(user.identifier, batchId))
    except BatchNotFound:
        raise not_found() from None
    return Response(
        content,
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="filas-excluidas.xlsx"'},
    )


class Recipient(BaseModel):
    kind: Literal["test"]
    label: str


class EmailTemplate(BaseModel):
    subject: str
    body: str
    isFinal: bool
    pendingDecision: str | None


class ConfirmationSummary(BaseModel):
    batchId: str
    reviewedVersion: Sha256
    incidentsToCreate: int = Field(ge=0)
    emailsToGenerate: int = Field(ge=0)
    withoutEmail: int = Field(ge=0)
    excluded: int = Field(ge=0)
    recipient: Recipient
    template: EmailTemplate


class ConfirmRequest(BaseModel):
    reviewedVersion: Sha256


class ExcludedRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rowNumber: int = Field(ge=1)
    row_class: RowClass = Field(alias="class")
    reason: str


class ConfirmationResult(BaseModel):
    batchId: str
    confirmedAt: datetime
    createdIncidents: int = Field(ge=0)
    pendingEmails: int = Field(ge=0)
    withoutEmail: int = Field(ge=0)
    excluded: list[ExcludedRow]
    excludedAtConfirmation: list[ExcludedRow]
    alreadyConfirmed: bool


def authorized_email(request: Request) -> AuthorizedEmail | None:
    """The recipient and template authorized now: only the configured test recipient (P-01)."""
    recipient = request.app.state.settings.test_recipient_email
    if not recipient:
        return None
    return AuthorizedEmail(
        recipient=recipient,
        template_version=email_template.TEMPLATE_VERSION,
        subject=email_template.SUBJECT,
        body=email_template.BODY,
    )


def confirmation_service(request: Request) -> ConfirmationService:
    state = request.app.state
    if getattr(state, "confirmation_service", None) is None:
        from app.adapters.db.unit_of_work import SqlUnitOfWork

        state.confirmation_service = ConfirmationService(
            SqlUnitOfWork(state.engine), email=lambda: authorized_email(request)
        )
    service: ConfirmationService = state.confirmation_service
    return service


@router.get(
    "/api/batches/{batchId}/confirmation-summary",
    operation_id="getConfirmationSummary",
    response_model=ConfirmationSummary,
    responses={**SECURED, **NOT_FOUND},
)
def get_confirmation_summary(
    batchId: str, user: Importer, service: Annotated[BatchService, Depends(batch_service)]
) -> ConfirmationSummary:
    try:
        record = service.get(user.identifier, batchId)
    except BatchNotFound:
        raise not_found() from None
    if record.state != "in_review" or record.summary is None or record.sha256 is None:
        raise not_found()  # nothing prepared to confirm yet
    summary = record.summary
    return ConfirmationSummary(
        batchId=record.id,
        reviewedVersion=record.sha256,
        incidentsToCreate=summary.new,
        emailsToGenerate=summary.emails_to_generate,
        withoutEmail=summary.without_email,
        excluded=summary.duplicate + summary.conflict + summary.error,
        recipient=Recipient(kind="test", label="Destinatario de prueba"),
        template=EmailTemplate(
            subject=email_template.SUBJECT,
            body=email_template.BODY,
            isFinal=False,
            pendingDecision=email_template.PENDING_DECISION,
        ),
    )


@router.post(
    "/api/batches/{batchId}/confirm",
    operation_id="confirmBatch",
    response_model=ConfirmationResult,
    responses={**SECURED, **NOT_FOUND, **CONFLICT, **UNPROCESSABLE},
)
def confirm_batch(
    batchId: str,
    body: ConfirmRequest,
    user: Confirmer,
    service: Annotated[ConfirmationService, Depends(confirmation_service)],
) -> ConfirmationResult:
    try:
        result = service.confirm(user.identifier, batchId, body.reviewedVersion)
    except BatchNotFound:
        raise not_found() from None
    except BatchNotConfirmable as exc:
        if exc.discarded:
            raise ApiError(
                409,
                {
                    "code": "batch_discarded",
                    "message": "El lote fue descartado y ya no se puede confirmar.",
                },
            ) from None
        raise ApiError(
            409,
            {"code": "batch_not_reviewable", "message": "El lote no está listo para confirmarse."},
        ) from None
    except ReviewedVersionMismatch:
        raise ApiError(
            422,
            {
                "code": "reviewed_version_mismatch",
                "message": "La versión revisada no coincide con el archivo subido.",
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
    return ConfirmationResult.model_validate(result)
