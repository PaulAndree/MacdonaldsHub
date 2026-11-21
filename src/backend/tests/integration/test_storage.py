import uuid

import httpx
import pytest
from azure.storage.blob import BlobServiceClient

from app.adapters.storage.blob import BlobStorageService, account_key_signer
from app.services.ports import CONFIRMED, UPLOADS, ImmutableContainerError

pytestmark = pytest.mark.integration

ORIGIN = "http://localhost:3000"


@pytest.fixture
def storage(azurite_connection_string: str) -> BlobStorageService:
    client = BlobServiceClient.from_connection_string(azurite_connection_string)
    service = BlobStorageService(client, account_key_signer(client, client.credential.account_key))
    service.ensure_containers()
    service.ensure_cors(ORIGIN)
    return service


def name() -> str:
    return f"technical/{uuid.uuid4().hex}"


def put(grant, body: bytes = b"hello", url: str | None = None) -> httpx.Response:  # type: ignore[no-untyped-def]
    return httpx.request(
        grant.method, url or grant.url, content=body, headers={**grant.headers, "Origin": ORIGIN}
    )


def test_containers_exist(storage: BlobStorageService) -> None:
    assert storage._client.get_container_client(UPLOADS).exists()
    assert storage._client.get_container_client(CONFIRMED).exists()


def test_upload_with_grant_and_identify_file(storage: BlobStorageService) -> None:
    blob = name()
    assert storage.get_blob_info(UPLOADS, blob) is None
    grant = storage.issue_upload_grant(blob)
    assert grant.method == "PUT"

    resp = put(grant, b"technical-file")
    assert resp.status_code == 201, resp.text

    info = storage.get_blob_info(UPLOADS, blob)
    assert info is not None and info.size == len(b"technical-file") and info.etag


def test_grant_cannot_overwrite_an_existing_blob(storage: BlobStorageService) -> None:
    blob = name()
    grant = storage.issue_upload_grant(blob)
    assert put(grant, b"original").status_code == 201

    again = put(grant, b"replacement")
    assert again.status_code in (403, 409, 412), again.text

    downloaded = storage._client.get_blob_client(UPLOADS, blob).download_blob().readall()
    assert downloaded == b"original"


def test_grant_for_a_different_blob_name_is_rejected(storage: BlobStorageService) -> None:
    grant = storage.issue_upload_grant(name())
    other = name()
    forged_url = grant.url.replace(grant.blob_name, other)
    assert put(grant, url=forged_url).status_code == 403
    assert storage.get_blob_info(UPLOADS, other) is None


def test_grant_cannot_read_or_delete(storage: BlobStorageService) -> None:
    blob = name()
    grant = storage.issue_upload_grant(blob)
    assert put(grant).status_code == 201
    assert httpx.get(grant.url).status_code == 403
    assert httpx.delete(grant.url).status_code == 403
    assert storage.get_blob_info(UPLOADS, blob) is not None


def test_grant_cannot_target_the_confirmed_container(storage: BlobStorageService) -> None:
    grant = storage.issue_upload_grant(name())
    forged = grant.url.replace(f"/{UPLOADS}/", f"/{CONFIRMED}/")
    assert put(grant, url=forged).status_code == 403


def test_delete_in_confirmed_is_refused_and_blob_survives(storage: BlobStorageService) -> None:
    blob = name()
    storage._client.get_blob_client(CONFIRMED, blob).upload_blob(b"keep", overwrite=True)
    with pytest.raises(ImmutableContainerError):
        storage.delete_blob(CONFIRMED, blob)
    assert storage.get_blob_info(CONFIRMED, blob) is not None


def test_delete_in_uploads_is_allowed(storage: BlobStorageService) -> None:
    blob = name()
    grant = storage.issue_upload_grant(blob)
    assert put(grant).status_code == 201
    storage.delete_blob(UPLOADS, blob)
    assert storage.get_blob_info(UPLOADS, blob) is None


def test_cors_allows_only_the_frontend_origin(storage: BlobStorageService) -> None:
    grant = storage.issue_upload_grant(name())
    url = grant.url

    def preflight(origin: str) -> httpx.Response:
        return httpx.options(
            url,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "x-ms-blob-type,if-none-match",
            },
        )

    ok = preflight(ORIGIN)
    assert ok.status_code == 200
    assert ok.headers.get("access-control-allow-origin") == ORIGIN

    bad = preflight("http://evil.example")
    assert bad.headers.get("access-control-allow-origin") != "http://evil.example"
    assert bad.status_code in (200, 403)


def test_grant_url_uses_the_public_endpoint_when_configured(azurite_connection_string: str) -> None:
    client = BlobServiceClient.from_connection_string(azurite_connection_string)
    internal = BlobStorageService(
        client,
        account_key_signer(client, client.credential.account_key),
        public_endpoint="http://browser-facing.test:10000/devstoreaccount1/",
    )
    blob = name()
    grant = internal.issue_upload_grant(blob)
    assert grant.url.startswith(
        f"http://browser-facing.test:10000/devstoreaccount1/uploads/{blob}?"
    )
    # The signature does not depend on the host, so the same query works on the real endpoint.
    query = grant.url.split("?", 1)[1]
    ok = httpx.put(
        f"{client.get_blob_client(UPLOADS, blob).url}?{query}", content=b"x", headers=grant.headers
    )
    assert ok.status_code == 201, ok.text
