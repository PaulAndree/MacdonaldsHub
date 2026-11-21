from urllib.parse import parse_qs, urlparse

from azure.core.credentials import AccessToken
from azure.storage.blob import BlobServiceClient, UserDelegationKey

from app.adapters.storage.blob import BlobStorageService, user_delegation_signer
from app.services.ports import CONFIRMED


class FakeCredential:
    def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        raise AssertionError("no network call expected")


def service(monkeypatch) -> tuple[BlobStorageService, list[tuple[object, object]]]:  # type: ignore[no-untyped-def]
    client = BlobServiceClient(
        "https://acct.blob.core.windows.net",
        credential=FakeCredential(),  # type: ignore[arg-type]
    )
    calls: list[tuple[object, object]] = []

    def fake_key(start, expiry, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((start, expiry))
        key = UserDelegationKey()
        key.signed_oid = "oid-1"
        key.signed_tid = "tid-1"
        key.signed_start = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        key.signed_expiry = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
        key.signed_service = "b"
        key.signed_version = "2023-11-03"
        key.value = "c2VjcmV0LWRlbGVnYXRpb24ta2V5"
        return key

    monkeypatch.setattr(client, "get_user_delegation_key", fake_key)
    return BlobStorageService(client, user_delegation_signer(client)), calls


def test_grant_is_create_only_for_one_blob_with_managed_identity_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    svc, calls = service(monkeypatch)
    grant = svc.issue_upload_grant("technical/abc")

    url = urlparse(grant.url)
    q = parse_qs(url.query)
    assert url.netloc == "acct.blob.core.windows.net"
    assert url.path == "/uploads/technical/abc"
    assert q["sp"] == ["c"]  # create only: no read, write, delete
    assert q["sr"] == ["b"]  # a single blob
    assert q["skoid"] == ["oid-1"]  # signed with a user delegation key, not an account key
    assert "sig" in q
    assert grant.headers["If-None-Match"] == "*"
    assert len(calls) == 1
    assert (grant.expires_at - calls[0][0]).total_seconds() <= 20 * 60  # type: ignore[operator]


def test_delete_in_confirmed_is_refused_without_calling_storage(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import pytest

    from app.services.ports import ImmutableContainerError

    svc, _ = service(monkeypatch)
    with pytest.raises(ImmutableContainerError):
        svc.delete_blob(CONFIRMED, "any")
