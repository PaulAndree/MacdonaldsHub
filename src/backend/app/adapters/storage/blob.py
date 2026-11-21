"""Blob storage adapter: Azurite locally, Azure Blob with managed identity in Azure.

The upload grant is a SAS limited to ONE blob, create-only (no read, no overwrite, no
delete), short lived. Blob names are generated server side by the caller.
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from urllib.parse import quote

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    CorsRule,
    generate_blob_sas,
)

from app.domain.clock import utc_now
from app.services.ports import (
    CONFIRMED,
    UPLOADS,
    BlobInfo,
    ImmutableContainerError,
    UploadGrant,
)

GRANT_TTL = timedelta(minutes=15)
_SKEW = timedelta(minutes=5)

# (container, blob, start, expiry) -> SAS query string
Signer = Callable[[str, str, datetime, datetime], str]


class BlobStorageService:
    def __init__(
        self, client: BlobServiceClient, signer: Signer, public_endpoint: str | None = None
    ) -> None:
        self._client = client
        self._sign = signer
        self._public_endpoint = public_endpoint.rstrip("/") if public_endpoint else None

    def ensure_containers(self) -> None:
        """Create `uploads` and `confirmed` if missing (Azure creates them with Bicep)."""
        for name in (UPLOADS, CONFIRMED):
            container = self._client.get_container_client(name)
            if not container.exists():
                container.create_container()

    def ensure_cors(self, allowed_origin: str) -> None:
        """Allow the browser to PUT directly from the frontend origin only (local Azurite)."""
        self._client.set_service_properties(
            cors=[
                CorsRule(
                    allowed_origins=[allowed_origin],
                    allowed_methods=["PUT", "OPTIONS"],
                    allowed_headers=["*"],
                    exposed_headers=["*"],
                    max_age_in_seconds=600,
                )
            ]
        )

    def issue_upload_grant(self, blob_name: str) -> UploadGrant:
        now = utc_now()
        expires = now + GRANT_TTL
        sas = self._sign(UPLOADS, blob_name, now - _SKEW, expires)
        base = (
            f"{self._public_endpoint}/{UPLOADS}/{quote(blob_name)}"
            if self._public_endpoint
            else self._client.get_blob_client(UPLOADS, blob_name).url
        )
        url = f"{base}?{sas}"
        return UploadGrant(
            blob_name=blob_name,
            url=url,
            method="PUT",
            headers={"x-ms-blob-type": "BlockBlob", "If-None-Match": "*"},
            expires_at=expires,
        )

    def get_blob_info(self, container: str, blob_name: str) -> BlobInfo | None:
        try:
            props = self._client.get_blob_client(container, blob_name).get_blob_properties()
        except ResourceNotFoundError:
            return None
        return BlobInfo(
            container=container,
            name=blob_name,
            size=props.size,
            etag=props.etag,
            content_type=props.content_settings.content_type,
        )

    def delete_blob(self, container: str, blob_name: str) -> None:
        if container == CONFIRMED:
            # Mirrors the container-level immutability Azure enforces; Azurite cannot (P-05).
            raise ImmutableContainerError("Blobs in the 'confirmed' container are immutable")
        self._client.get_blob_client(container, blob_name).delete_blob()


def create_only_permission() -> BlobSasPermissions:
    return BlobSasPermissions(create=True)


def account_key_signer(client: BlobServiceClient, account_key: str) -> Signer:
    def sign(container: str, blob: str, start: datetime, expiry: datetime) -> str:
        return generate_blob_sas(
            account_name=str(client.account_name),
            container_name=container,
            blob_name=blob,
            account_key=account_key,
            permission=create_only_permission(),
            start=start,
            expiry=expiry,
        )

    return sign


def user_delegation_signer(client: BlobServiceClient) -> Signer:
    def sign(container: str, blob: str, start: datetime, expiry: datetime) -> str:
        key = client.get_user_delegation_key(start, expiry)
        return generate_blob_sas(
            account_name=str(client.account_name),
            container_name=container,
            blob_name=blob,
            user_delegation_key=key,
            permission=create_only_permission(),
            start=start,
            expiry=expiry,
        )

    return sign
