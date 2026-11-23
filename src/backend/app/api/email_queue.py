"""The email queue operations of the approved contract: read it, pause it, resume it."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.errors import SECURED
from app.api.security import require_permission
from app.domain.mail_rules import unavailable_reason
from app.services.authorization import AuthorizedUser
from app.services.mail_queue import QueueService, Status

router = APIRouter(tags=["email-queue"])

Controller = Annotated[AuthorizedUser, Depends(require_permission("queue_control"))]
EmailState = Literal["pending", "sending", "sent", "error"]


class QueueStatus(BaseModel):
    paused: bool
    pausedAt: datetime | None
    inFlight: int = Field(ge=0)
    sendingAvailable: bool
    unavailableReason: str | None


class EmailTotals(BaseModel):
    pending: int = Field(ge=0)
    sending: int = Field(ge=0)
    sent: int = Field(ge=0)
    error: int = Field(ge=0)


class Recipient(BaseModel):
    kind: Literal["test"]
    label: str


class QueueEntry(BaseModel):
    id: str
    incidentId: str
    batchId: str | None
    orderId: str
    provider: Literal["uber eats", "just eat", "glovo"]
    state: EmailState
    reason: str | None
    errorKind: Literal["send_failed", "interrupted_unverified"] | None
    startedAt: datetime | None
    finishedAt: datetime | None
    recipient: Recipient


class BatchEmailProgress(BaseModel):
    batchId: str
    completed: bool
    totals: EmailTotals


class QueueView(BaseModel):
    status: QueueStatus
    minIntervalSeconds: Literal[30]
    attemptsPerEmail: Literal[1]
    nextEligibleAt: datetime | None
    totals: EmailTotals
    batches: list[BatchEmailProgress]
    items: list[QueueEntry]
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1)
    total: int = Field(ge=0)


def queue_service(request: Request) -> QueueService:
    state = request.app.state
    if getattr(state, "queue_service", None) is None:
        from app.adapters.db.mail_queue import SqlQueueRepository

        def unavailable() -> str | None:
            s = state.settings  # read each time: the configuration is what decides
            return unavailable_reason(s.app_env, s.smtp_host, s.smtp_from, s.test_recipient_email)

        state.queue_service = QueueService(SqlQueueRepository(state.engine), unavailable)
    service: QueueService = state.queue_service
    return service


def _status(status: Status) -> QueueStatus:
    return QueueStatus(
        paused=status.paused,
        pausedAt=status.paused_at,
        inFlight=status.in_flight,
        sendingAvailable=status.sending_available,
        unavailableReason=status.unavailable_reason,
    )


@router.get(
    "/api/email-queue",
    operation_id="getEmailQueue",
    response_model=QueueView,
    responses=SECURED,
)
def get_email_queue(
    user: Controller,
    service: Annotated[QueueService, Depends(queue_service)],
    state: Annotated[EmailState | None, Query()] = None,
    batchId: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=200)] = 50,
) -> QueueView:
    view = service.view(state, batchId, page, pageSize)
    return QueueView(
        status=_status(view.status),
        minIntervalSeconds=30,
        attemptsPerEmail=1,
        nextEligibleAt=view.next_eligible_at,
        totals=EmailTotals(**vars(view.totals)),
        batches=[
            BatchEmailProgress(
                batchId=b.batch_id, completed=b.completed, totals=EmailTotals(**vars(b.totals))
            )
            for b in view.batches
        ],
        items=[
            QueueEntry(
                id=e.id,
                incidentId=e.incident_id,
                batchId=e.batch_id,
                orderId=e.order_id,
                provider=e.provider,  # type: ignore[arg-type]
                state=e.state,  # type: ignore[arg-type]
                reason=e.reason,
                errorKind=e.error_kind,  # type: ignore[arg-type]
                startedAt=e.started_at,
                finishedAt=e.finished_at,
                # Until real recipients are defined the only one is the test recipient (P-01).
                recipient=Recipient(kind="test", label="Destinatario de prueba"),
            )
            for e in view.items
        ],
        page=view.page,
        pageSize=view.page_size,
        total=view.total,
    )


@router.post(
    "/api/email-queue/pause",
    operation_id="pauseEmailQueue",
    response_model=QueueStatus,
    responses=SECURED,
)
def pause_email_queue(
    user: Controller, service: Annotated[QueueService, Depends(queue_service)]
) -> QueueStatus:
    return _status(service.pause(user.identifier))


@router.post(
    "/api/email-queue/resume",
    operation_id="resumeEmailQueue",
    response_model=QueueStatus,
    responses=SECURED,
)
def resume_email_queue(
    user: Controller, service: Annotated[QueueService, Depends(queue_service)]
) -> QueueStatus:
    return _status(service.resume(user.identifier))
