"""Technical flow endpoints (platform base only): identity, PostgreSQL and storage checks.

They verify connectivity and permissions; they create no business data and anticipate no
functional design.
"""

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.adapters.db.models import TechnicalCheck
from app.api.security import current_user, require_role
from app.domain.clock import to_madrid
from app.services.authorization import AuthorizedUser
from app.services.ports import UPLOADS, StorageService

router = APIRouter(prefix="/api/technical", tags=["technical"])

_ID = re.compile(r"^[0-9a-f]{32}$")
Admin = Annotated[AuthorizedUser, Depends(require_role("administrator"))]
AnyUser = Annotated[AuthorizedUser, Depends(current_user)]


def _blob_name(upload_id: str) -> str:
    return f"technical/{upload_id}"


@router.get("/me")
def me(user: AnyUser) -> dict[str, str | None]:
    return {"identifier": user.identifier, "email": user.email, "role": user.role}


@router.post("/check")
def check(request: Request, user: Admin) -> dict[str, object]:
    """Round trip screen -> API -> PostgreSQL: records a technical check and reads it back."""
    engine: Engine = request.app.state.engine
    with Session(engine) as session, session.begin():
        row = TechnicalCheck(actor=user.identifier)
        session.add(row)
        session.flush()
        total = session.scalar(select(func.count()).select_from(TechnicalCheck))
        created = session.scalar(
            select(TechnicalCheck.created_at).where(TechnicalCheck.id == row.id)
        )
        check_id = str(row.id)
    assert created is not None
    return {
        "status": "ok",
        "database": "ok",
        "check_id": check_id,
        "checks_total": total,
        "recorded_at": to_madrid(created).isoformat(),
    }


@router.post("/upload-grants")
def create_upload_grant(request: Request, user: Admin) -> dict[str, object]:
    storage: StorageService = request.app.state.container.storage()
    upload_id = uuid.uuid4().hex  # generated server side: the browser never picks the blob name
    grant = storage.issue_upload_grant(_blob_name(upload_id))
    return {
        "upload_id": upload_id,
        "url": grant.url,
        "method": grant.method,
        "headers": grant.headers,
        "expires_at": grant.expires_at.isoformat(),
    }


@router.get("/uploads/{upload_id}")
def get_upload(upload_id: str, request: Request, user: Admin) -> dict[str, object]:
    if not _ID.match(upload_id):
        raise HTTPException(status_code=404, detail="Upload not found")
    storage: StorageService = request.app.state.container.storage()
    info = storage.get_blob_info(UPLOADS, _blob_name(upload_id))
    if info is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"upload_id": upload_id, "container": info.container, "size": info.size}
