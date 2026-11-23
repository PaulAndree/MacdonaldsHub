"""Upload grant and registration with real PostgreSQL and Azurite (RF-01, ADR-14, E-01)."""

from typing import Any

import httpx
import pytest
from sqlalchemy import text

from tests.integration.test_api import azure_like_settings, client_for, principal_headers, reset

pytestmark = pytest.mark.integration

ADMIN = "admin@example.test"
OTHER = "other-admin@example.test"
MANAGER = "manager@example.test"
BODY = {"fileName": "incidencias.xlsx", "sizeBytes": 14}


@pytest.fixture
def client(database_url: str, azurite_connection_string: str):  # type: ignore[no-untyped-def]
    reset(database_url)
    test_client, engine = client_for(
        azure_like_settings(database_url, azurite_connection_string), database_url
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), :a, :a, 'administrator'), "
                "(gen_random_uuid(), :o, :o, 'administrator'), "
                "(gen_random_uuid(), :m, :m, 'global_manager')"
            ),
            {"a": ADMIN, "o": OTHER, "m": MANAGER},
        )
    test_client.engine = engine  # type: ignore[attr-defined]
    yield test_client
    engine.dispose()


def create(client: Any, who: str = ADMIN) -> dict[str, Any]:
    response = client.post("/api/batches", json=BODY, headers=principal_headers(who))
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def put(upload: dict[str, Any], content: bytes = b"synthetic xlsx") -> httpx.Response:
    return httpx.request(
        upload["method"], upload["url"], content=content, headers=upload["headers"]
    )


def test_a_batch_is_registered_with_a_create_only_grant(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    batch = created["batch"]
    assert batch["state"] == "uploaded"
    assert batch["fileName"] == "incidencias.xlsx"
    assert batch["reviewedVersion"] is None and batch["rejection"] is None
    assert batch["identicalFile"] is None and batch["summary"] is None
    assert created["upload"]["method"] == "PUT"
    assert created["upload"]["headers"]["If-None-Match"] == "*"
    assert put(created["upload"]).status_code == 201


def test_the_stored_blob_name_is_chosen_by_the_server_and_belongs_to_the_batch(client) -> None:  # type: ignore[no-untyped-def]
    batch = create(client)["batch"]
    with client.engine.connect() as conn:
        name = conn.execute(text("SELECT blob_name FROM batch")).scalar()
    assert name == f"batches/{batch['id']}.xlsx"
    assert "incidencias" not in name  # the browser's file name never becomes the blob name


def test_a_second_upload_cannot_overwrite_the_first(client) -> None:  # type: ignore[no-untyped-def]
    upload = create(client)["upload"]
    assert put(upload, b"first").status_code == 201
    second = put(upload, b"second")
    # A create-only permission cannot replace a blob: the store refuses (403) or reports it exists.
    assert second.status_code in (403, 409, 412)
    storage = client.app.state.container.storage()
    with client.engine.connect() as conn:
        name = conn.execute(text("SELECT blob_name FROM batch")).scalar()
    assert storage.get_blob_info("uploads", name).size == len(b"first")


def test_a_grant_cannot_write_a_blob_it_was_not_made_for(client) -> None:  # type: ignore[no-untyped-def]
    upload = create(client)["upload"]
    other_blob = upload["url"].replace("batches/", "batches/x-")
    response = httpx.request("PUT", other_blob, content=b"x", headers=upload["headers"])
    assert response.status_code in (403, 404)


def test_completing_the_upload_requests_processing(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    put(created["upload"])
    done = client.post(
        f"/api/batches/{created['batch']['id']}/uploaded", headers=principal_headers(ADMIN)
    )
    assert done.status_code == 202
    assert done.json()["state"] == "processing"
    fetched = client.get(f"/api/batches/{created['batch']['id']}", headers=principal_headers(ADMIN))
    assert fetched.json()["state"] == "processing"


def test_completing_without_a_file_in_storage_is_refused(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    response = client.post(
        f"/api/batches/{created['batch']['id']}/uploaded", headers=principal_headers(ADMIN)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "upload_not_found"
    state = client.get(f"/api/batches/{created['batch']['id']}", headers=principal_headers(ADMIN))
    assert state.json()["state"] == "uploaded"


def test_another_users_batch_cannot_be_completed_or_read(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    put(created["upload"])
    batch_id = created["batch"]["id"]
    assert (
        client.post(
            f"/api/batches/{batch_id}/uploaded", headers=principal_headers(OTHER)
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/batches/{batch_id}", headers=principal_headers(OTHER)).status_code == 404
    )
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT state FROM batch")).scalar() == "uploaded"


@pytest.mark.parametrize("reference", ["lote-0001", "../x", "00000000-0000-0000-0000-000000000000"])
def test_an_unknown_batch_reference_is_not_found(client, reference: str) -> None:  # type: ignore[no-untyped-def]
    headers = principal_headers(ADMIN)
    assert client.get(f"/api/batches/{reference}", headers=headers).status_code == 404
    assert client.post(f"/api/batches/{reference}/uploaded", headers=headers).status_code == 404


def test_no_incident_or_outbox_exists_after_uploading(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    put(created["upload"])
    client.post(f"/api/batches/{created['batch']['id']}/uploaded", headers=principal_headers(ADMIN))
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM outbox")).scalar() == 0


def test_a_user_with_an_unconfirmed_batch_gets_a_409_naming_it(client) -> None:  # type: ignore[no-untyped-def]
    first = create(client)["batch"]["id"]
    response = client.post("/api/batches", json=BODY, headers=principal_headers(ADMIN))
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "unconfirmed_batch_exists"
    assert body["details"] == {"batchId": first}


def test_a_global_manager_cannot_register_a_batch(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/batches", json=BODY, headers=principal_headers(MANAGER))
    assert response.status_code == 403
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM batch")).scalar() == 0


def test_the_request_must_have_a_name_and_a_size(client) -> None:  # type: ignore[no-untyped-def]
    headers = principal_headers(ADMIN)
    assert (
        client.post(
            "/api/batches", json={"fileName": "", "sizeBytes": 1}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/batches", json={"fileName": "a.xlsx", "sizeBytes": -1}, headers=headers
        ).status_code
        == 422
    )
    assert client.post("/api/batches", json={}, headers=headers).status_code == 422


def test_the_operations_are_audited(client) -> None:  # type: ignore[no-untyped-def]
    created = create(client)
    put(created["upload"])
    client.post(f"/api/batches/{created['batch']['id']}/uploaded", headers=principal_headers(ADMIN))
    with client.engine.connect() as conn:
        rows = conn.execute(text("SELECT actor, operation FROM audit_log ORDER BY id")).all()
    assert rows == [(ADMIN, "batch.create"), (ADMIN, "batch.upload_complete")]
