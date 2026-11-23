"""Authentication and authorization middleware, deny by default.

Order matters: 401 when there is no identity (before any allowlist lookup), then 403 when
the identity is not allowlisted, then role checks per operation.
"""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.domain.permissions import Permission, can
from app.domain.roles import Role
from app.services.authorization import AuthorizedUser, Authorizer
from app.services.ports import IdentityProvider

PUBLIC_PATHS = frozenset({"/healthz", "/readyz"})

# Errors use the `Error` schema of the approved contract (code and a message for the user).
NOT_AUTHENTICATED = {
    "code": "not_authenticated",
    "message": "Sesión no válida. Recargue la página para iniciar sesión.",
}
NOT_AUTHORIZED = {
    "code": "not_authorized",
    "message": "Acceso denegado: su usuario no tiene permiso para esta operación.",
}


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
            return JSONResponse(NOT_AUTHENTICATED, status_code=401)
        user = self._authorizer.authorize(identity)
        if user is None:
            return JSONResponse(NOT_AUTHORIZED, status_code=403)
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


class ApiError(Exception):
    """An error answered with the contract's `Error` body."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        super().__init__(body["code"])
        self.status_code = status_code
        self.body = body


async def api_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return JSONResponse(exc.body, status_code=exc.status_code)


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """A malformed request answers with the contract's Error body, not FastAPI's own shape."""
    return JSONResponse(
        {"code": "invalid_request", "message": "La solicitud no es válida."}, status_code=422
    )


def require_permission(permission: Permission) -> Callable[..., AuthorizedUser]:
    """Authorizes one operation by the permission matrix. A refusal changes nothing (BE-08).

    The frontend hiding an action is only a convenience: this is where it is actually decided.
    """

    def dependency(user: Annotated[AuthorizedUser, Depends(current_user)]) -> AuthorizedUser:
        if not can(user.role, permission):
            raise ApiError(403, NOT_AUTHORIZED)
        return user

    return dependency
