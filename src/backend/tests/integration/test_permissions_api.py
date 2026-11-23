"""Permissions enforced by the API for every operation (RNF-04, BE-08, UI-10)."""

from typing import Annotated, Any

import pytest
from fastapi import Depends
from sqlalchemy import text

from app.api.security import require_permission
from app.services.authorization import AuthorizedUser
from tests.integration.test_api import azure_like_settings, client_for, principal_headers, reset

pytestmark = pytest.mark.integration

ADMIN = "admin@example.test"
MANAGER = "manager@example.test"
STRANGER = "stranger@example.test"
WRITE = ("import", "confirm", "incidents_write", "queue_control")
READ = ("incidents_read", "metrics_read")


def add_probe_routes(app: Any) -> None:
    """One probe route per permission, standing for the operations that need it."""
    for permission in (*WRITE, *READ):

        def make(name: str) -> None:
            def handler(
                user: Annotated[AuthorizedUser, Depends(require_permission(name))],  # type: ignore[arg-type]
            ) -> dict[str, str]:
                return {"ok": user.identifier}

            app.add_api_route(f"/api/_probe/{name}", handler, methods=["POST"])

        make(permission)


@pytest.fixture
def client(database_url: str, azurite_connection_string: str):  # type: ignore[no-untyped-def]
    reset(database_url)
    settings = azure_like_settings(database_url, azurite_connection_string)
    test_client, engine = client_for(settings, database_url)
    add_probe_routes(test_client.app)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), :a, :a, 'administrator'), "
                "(gen_random_uuid(), :m, :m, 'global_manager')"
            ),
            {"a": ADMIN, "m": MANAGER},
        )
    test_client.engine = engine  # type: ignore[attr-defined]
    yield test_client
    engine.dispose()


@pytest.mark.parametrize("permission", [*WRITE, *READ])
def test_the_administrator_may_do_everything(client, permission: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post(f"/api/_probe/{permission}", headers=principal_headers(ADMIN))
    assert response.status_code == 200


@pytest.mark.parametrize("permission", WRITE)
def test_a_global_manager_that_changes_something_is_refused(client, permission: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post(f"/api/_probe/{permission}", headers=principal_headers(MANAGER))
    assert response.status_code == 403
    assert response.json()["code"] == "not_authorized"


@pytest.mark.parametrize("permission", READ)
def test_a_global_manager_may_read(client, permission: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post(f"/api/_probe/{permission}", headers=principal_headers(MANAGER))
    assert response.status_code == 200


@pytest.mark.parametrize("permission", [*WRITE, *READ])
def test_an_identity_outside_the_allowlist_is_refused_everywhere(client, permission: str) -> None:  # type: ignore[no-untyped-def]
    response = client.post(f"/api/_probe/{permission}", headers=principal_headers(STRANGER))
    assert response.status_code == 403
    assert response.json()["code"] == "not_authorized"


def test_a_request_without_identity_is_a_401_in_the_contract_error_shape(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/_probe/import")
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "not_authenticated"
    assert isinstance(body["message"], str) and body["message"]


def test_a_deactivated_identity_loses_access_on_the_next_call(client) -> None:  # type: ignore[no-untyped-def]
    headers = principal_headers(ADMIN)
    assert client.post("/api/_probe/import", headers=headers).status_code == 200
    with client.engine.begin() as conn:  # type: ignore[attr-defined]
        conn.execute(
            text("UPDATE allowlist_entry SET active = false WHERE identifier = :a"), {"a": ADMIN}
        )
    assert client.post("/api/_probe/import", headers=headers).status_code == 403


def test_a_refused_operation_changes_nothing(client) -> None:  # type: ignore[no-untyped-def]
    client.post("/api/_probe/confirm", headers=principal_headers(MANAGER))
    with client.engine.begin() as conn:  # type: ignore[attr-defined]
        assert conn.execute(text("SELECT count(*) FROM audit_log")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 0


def test_the_session_reports_role_environment_and_permissions(client) -> None:  # type: ignore[no-untyped-def]
    admin = client.get("/api/session", headers=principal_headers(ADMIN)).json()
    assert admin["role"] == "administrator"
    assert admin["environment"] == "test"
    assert admin["email"] == ADMIN
    assert set(admin["permissions"]) == {*WRITE, *READ}

    manager = client.get("/api/session", headers=principal_headers(MANAGER)).json()
    assert manager["role"] == "global_manager"
    assert set(manager["permissions"]) == set(READ)


def test_the_session_of_an_unauthorized_identity_is_a_403(client) -> None:  # type: ignore[no-untyped-def]
    response = client.get("/api/session", headers=principal_headers(STRANGER))
    assert response.status_code == 403
    assert response.json()["code"] == "not_authorized"


def test_the_api_offers_no_operation_to_manage_the_allowlist(client) -> None:  # type: ignore[no-untyped-def]
    paths = [p for p in client.app.openapi()["paths"] if not p.startswith("/api/_probe")]
    assert not any("allowlist" in p or "admin" in p or "audit" in p for p in paths)
