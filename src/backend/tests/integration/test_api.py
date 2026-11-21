import base64
import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.adapters.db.allowlist import seed_initial_admin
from app.adapters.db.engine import make_engine
from app.adapters.registry import default_registry
from app.api.main import build_app
from app.composition import Container
from app.migrate import run
from app.settings import Settings

pytestmark = pytest.mark.integration

EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"


def local_settings(db: str, blob: str, role: str = "administrator") -> Settings:
    return Settings(
        _env_file=None,
        app_env="local",
        identity_provider="dev",
        dev_identity_email="dev@example.test",
        dev_identity_role=role,
        storage_backend="azurite",
        storage_connection_string=blob,
        mail_transport="smtp_capture",
        telemetry_exporter="console",
        database_url=db,
        frontend_origin="http://localhost:3000",
    )  # type: ignore[arg-type]


def azure_like_settings(db: str, blob: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        database_auth="managed_identity",  # settings only; the test builds its own engine
        identity_provider="easy_auth",
        allowlist_identifier="email",
        initial_admin_email="admin@example.test",
        storage_backend="azurite",  # real Azurite stands in for Blob in this test
        storage_connection_string=blob,
        mail_transport="smtp_capture",
        telemetry_exporter="console",
        database_url=db,
        frontend_origin="http://localhost:3000",
    )  # type: ignore[arg-type]


def client_for(settings: Settings, db: str) -> tuple[TestClient, Any]:
    engine = make_engine(db)
    app = build_app(settings, Container(settings, default_registry()), engine)
    return TestClient(app), engine


def reset(db: str, migrate: bool = True) -> None:
    eng = make_engine(db)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    eng.dispose()
    if migrate:
        run("upgrade", db)


def principal_headers(email: str) -> dict[str, str]:
    body = {"auth_typ": "google", "claims": [{"typ": EMAIL_CLAIM, "val": email}]}
    return {
        "x-ms-client-principal": base64.b64encode(json.dumps(body).encode()).decode(),
        "x-ms-client-principal-id": f"sub-{email}",
        "x-ms-client-principal-idp": "google",
    }


def test_api_starts_without_applying_migrations(
    database_url: str, azurite_connection_string: str
) -> None:
    reset(database_url, migrate=False)
    client, engine = client_for(
        local_settings(database_url, azurite_connection_string), database_url
    )
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
    assert inspect(engine).get_table_names() == []  # the API never migrates


def test_readiness_fails_when_database_is_down(azurite_connection_string: str) -> None:
    bad = "postgresql+psycopg://postgres:x@127.0.0.1:1/none?connect_timeout=1"
    client, _ = client_for(local_settings(bad, azurite_connection_string), bad)
    assert client.get("/healthz").status_code == 200  # liveness does not need the database
    assert client.get("/readyz").status_code == 503


def test_technical_round_trip_screen_api_postgres(
    database_url: str, azurite_connection_string: str
) -> None:  # BASE-03
    reset(database_url)
    client, engine = client_for(
        local_settings(database_url, azurite_connection_string), database_url
    )

    assert client.get("/api/technical/me").json()["role"] == "administrator"
    first = client.post("/api/technical/check")
    second = client.post("/api/technical/check")
    assert first.status_code == 200 and first.json()["database"] == "ok"
    assert second.json()["checks_total"] == 2
    assert first.json()["recorded_at"].endswith(("+01:00", "+02:00"))  # Europe/Madrid
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM technical_check")).scalar_one() == 2


def test_technical_endpoints_require_administrator(
    database_url: str, azurite_connection_string: str
) -> None:
    reset(database_url)
    client, _ = client_for(
        local_settings(database_url, azurite_connection_string, role="global_manager"), database_url
    )
    assert client.get("/api/technical/me").status_code == 200
    assert client.post("/api/technical/check").status_code == 403
    assert client.post("/api/technical/upload-grants").status_code == 403


def test_technical_upload_lands_in_storage_and_creates_no_incident(
    database_url: str, azurite_connection_string: str
) -> None:  # BASE-05
    reset(database_url)
    client, engine = client_for(
        local_settings(database_url, azurite_connection_string), database_url
    )
    with engine.connect() as conn:
        before = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).all()

    grant = client.post("/api/technical/upload-grants").json()
    assert client.get(f"/api/technical/uploads/{grant['upload_id']}").status_code == 404

    put = httpx.request(
        grant["method"], grant["url"], content=b"technical file", headers=grant["headers"]
    )
    assert put.status_code == 201

    found = client.get(f"/api/technical/uploads/{grant['upload_id']}")
    assert found.status_code == 200
    assert found.json() == {
        "upload_id": grant["upload_id"],
        "container": "uploads",
        "size": len(b"technical file"),
    }
    with engine.connect() as conn:
        after = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).all()
        assert before == after  # no incident (or any business) table exists or was created
        assert conn.execute(text("SELECT count(*) FROM technical_check")).scalar_one() == 0


def test_browser_cannot_choose_the_blob_or_look_up_arbitrary_references(
    database_url: str, azurite_connection_string: str
) -> None:
    reset(database_url)
    client, _ = client_for(local_settings(database_url, azurite_connection_string), database_url)
    for bad in ("../secret", "technical%2Fabc", "ABC", "x" * 32, "g" * 32):
        assert client.get(f"/api/technical/uploads/{bad}").status_code == 404


def test_azure_mode_401_without_identity_403_for_unlisted_200_for_admin(
    database_url: str, azurite_connection_string: str
) -> None:  # BASE-02, BASE-12
    reset(database_url)
    settings = azure_like_settings(database_url, azurite_connection_string)
    client, engine = client_for(settings, database_url)
    seed_initial_admin(engine, "admin@example.test", "admin@example.test")

    assert client.get("/api/technical/me").status_code == 401
    assert client.get("/healthz").status_code == 200  # probes stay public

    unlisted = client.get("/api/technical/me", headers=principal_headers("stranger@example.test"))
    assert unlisted.status_code == 403

    ok = client.post("/api/technical/check", headers=principal_headers("admin@example.test"))
    assert ok.status_code == 200
    assert ok.json()["checks_total"] == 1


def test_azure_mode_non_google_or_garbage_identity_is_401(
    database_url: str, azurite_connection_string: str
) -> None:  # BASE-04
    reset(database_url)
    client, engine = client_for(
        azure_like_settings(database_url, azurite_connection_string), database_url
    )
    seed_initial_admin(engine, "admin@example.test")
    assert (
        client.get("/api/technical/me", headers={"x-ms-client-principal": "garbage"}).status_code
        == 401
    )
    forged = {"x-ms-client-principal-id": "x", "x-ms-client-principal-name": "admin@example.test"}
    assert client.get("/api/technical/me", headers=forged).status_code == 401
