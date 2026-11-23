"""The `Error` body of the approved contract and the documented error responses."""

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Stable code for the client and a message for the user, in Spanish."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


NOT_AUTHENTICATED_RESPONSE: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorBody, "description": "No valid session."}
}
FORBIDDEN_RESPONSE: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorBody, "description": "Authenticated but not authorized."}
}
# Every operation behind the session answers these two.
SECURED: dict[int | str, dict[str, Any]] = {**NOT_AUTHENTICATED_RESPONSE, **FORBIDDEN_RESPONSE}
UNPROCESSABLE: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorBody, "description": "The request cannot be processed as sent."}
}
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorBody, "description": "The object does not exist."}
}
CONFLICT: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorBody, "description": "The operation conflicts with the current state."}
}
