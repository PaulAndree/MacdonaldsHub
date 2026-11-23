"""Session: who is signed in, their role, the environment and what the role allows (getSession)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.errors import SECURED
from app.api.security import current_user
from app.domain.permissions import Permission, permissions_of
from app.domain.roles import Role
from app.services.authorization import AuthorizedUser

router = APIRouter(tags=["session"])


class Session(BaseModel):
    identifier: str
    email: str | None
    role: Role
    environment: Literal["local", "test", "production"]
    permissions: list[Permission]


@router.get("/api/session", operation_id="getSession", response_model=Session, responses=SECURED)
def get_session(
    request: Request, user: Annotated[AuthorizedUser, Depends(current_user)]
) -> Session:
    return Session(
        identifier=user.identifier,
        email=user.email,
        role=user.role,
        environment=request.app.state.settings.app_env,
        permissions=list(permissions_of(user.role)),
    )
