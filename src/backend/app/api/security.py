"""Authentication and authorization middleware, deny by default.

Order matters: 401 when there is no identity (before any allowlist lookup), then 403 when
the identity is not allowlisted, then role checks per operation.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.domain.roles import Role
from app.services.authorization import AuthorizedUser, Authorizer
from app.services.ports import IdentityProvider

PUBLIC_PATHS = frozenset({"/healthz", "/readyz"})


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, identity: IdentityProvider, authorizer: Authorizer) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._identity = identity
        self._authorizer = authorizer

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        headers = {k.lower(): v for k, v in request.headers.items()}
        identity = self._identity.resolve(headers)
        if identity is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        user = self._authorizer.authorize(identity)
        if user is None:
            return JSONResponse({"detail": "Access denied"}, status_code=403)
        request.state.user = user
        return await call_next(request)


def current_user(request: Request) -> AuthorizedUser:
    user: AuthorizedUser | None = getattr(request.state, "user", None)
    if user is None:  # pragma: no cover - middleware always sets it for protected paths
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: Role) -> Callable[..., AuthorizedUser]:
    def dependency(user: Annotated[AuthorizedUser, Depends(current_user)]) -> AuthorizedUser:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Operation not permitted for this role")
        return user

    return dependency
