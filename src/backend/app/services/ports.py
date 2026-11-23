"""Ports (interfaces) implemented by adapters. Business code depends only on these."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.domain.roles import Role


@dataclass(frozen=True)
class Identity:
    """An authenticated identity, before allowlist authorization."""

    subject: str | None = None
    email: str | None = None
    # Set only by the local development adapter; the allowlist is not consulted then.
    preauthorized_role: Role | None = None


@dataclass(frozen=True)
class AllowlistRecord:
    identifier: str
    role: Role


class AllowlistRepository(Protocol):
    def find_active(self, identifier: str) -> AllowlistRecord | None: ...


class IdentityProvider(Protocol):
    """Resolves the caller's identity from request headers; None means unauthenticated."""

    def resolve(self, headers: dict[str, str]) -> Identity | None: ...


UPLOADS = "uploads"
CONFIRMED = "confirmed"


class ImmutableContainerError(Exception):
    """Deleting or replacing blobs in the `confirmed` container is never allowed."""


@dataclass(frozen=True)
class UploadGrant:
    """Temporary, create-only permission for one blob in `uploads`, used directly by the browser."""

    blob_name: str
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class BlobInfo:
    container: str
    name: str
    size: int
    etag: str
    content_type: str | None


class StorageService(Protocol):
    """Blob storage access; Azurite locally, Azure Blob (managed identity) in Azure."""

    def issue_upload_grant(self, blob_name: str) -> UploadGrant: ...

    def get_blob_info(self, container: str, blob_name: str) -> BlobInfo | None: ...

    def read_blob(self, container: str, blob_name: str) -> bytes: ...

    def write_new_blob(self, container: str, blob_name: str, data: bytes) -> bool:
        """Create a blob, never replacing one: False when it already exists."""
        ...

    def delete_blob(self, container: str, blob_name: str) -> None: ...


class MailTransport(Protocol):
    """Outgoing mail transport. Sending is implemented in a later change."""


class TelemetryExporter(Protocol):
    def configure(self, service_name: str) -> None: ...


@dataclass(frozen=True)
class AuditEntry:
    """One audit record (RNF-05): who did what to which object, when, and how it ended."""

    actor: str  # the user's identifier, or "system:<task>" for worker actions
    at: datetime  # always a UTC instant
    operation: str
    object_type: str
    object_id: str | None
    outcome: str  # "success" or "failure"
    details: dict[str, Any] | None = None


class AuditLog(Protocol):
    """Appends records. It can only add: there is no operation to edit or remove one (RF-19)."""

    def record(self, entry: AuditEntry) -> None: ...
