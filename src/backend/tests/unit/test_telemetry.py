import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.api.security import AuthMiddleware
from app.api.telemetry import TelemetryMiddleware
from app.observability import SecretRedactionFilter, new_correlation_id, redact
from app.services.authorization import Authorizer
from app.services.ports import AllowlistRecord, Identity


class Repo:
    def find_active(self, identifier: str) -> AllowlistRecord | None:
        return AllowlistRecord(identifier, "administrator") if identifier == "ana@x.test" else None


class Ident:
    def resolve(self, headers: dict[str, str]) -> Identity | None:
        email = headers.get("x-user")
        return Identity(email=email) if email else None


@pytest.fixture
def setup() -> tuple[TestClient, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = FastAPI()
    app.add_middleware(AuthMiddleware, identity=Ident(), authorizer=Authorizer(Repo(), "email"))
    app.add_middleware(TelemetryMiddleware, tracer=provider.get_tracer("test"))

    @app.get("/api/ok")
    def ok() -> dict[str, str]:
        return {"x": "y"}

    @app.get("/api/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False), exporter


def last_log(caplog: pytest.LogCaptureFixture) -> dict[str, object]:
    records = [r for r in caplog.records if r.name == "app.access"]
    return json.loads(records[-1].getMessage())  # type: ignore[no-any-return]


def test_success_records_actor_correlation_and_result(
    setup: tuple[TestClient, InMemorySpanExporter], caplog: pytest.LogCaptureFixture
) -> None:
    client, exporter = setup
    with caplog.at_level(logging.INFO, logger="app.access"):
        r = client.get("/api/ok?token=abc", headers={"x-user": "ana@x.test"})
    log = last_log(caplog)
    assert log["actor"] == "ana@x.test" and log["result"] == "success" and log["status"] == 200
    assert log["correlation_id"] == r.headers["x-correlation-id"]
    assert "token" not in json.dumps(log)  # query string is not logged

    span = exporter.get_finished_spans()[-1]
    assert span.attributes["app.actor"] == "ana@x.test"  # type: ignore[index]
    assert span.attributes["app.correlation_id"] == log["correlation_id"]  # type: ignore[index]
    assert span.attributes["app.result"] == "success"  # type: ignore[index]


def test_denied_requests_are_traced_too(
    setup: tuple[TestClient, InMemorySpanExporter], caplog: pytest.LogCaptureFixture
) -> None:
    client, _ = setup
    with caplog.at_level(logging.INFO, logger="app.access"):
        assert client.get("/api/ok").status_code == 401
        anonymous = last_log(caplog)
        assert client.get("/api/ok", headers={"x-user": "eve@x.test"}).status_code == 403
        unlisted = last_log(caplog)
    assert anonymous["actor"] == "anonymous" and anonymous["result"] == "denied"
    assert unlisted["result"] == "denied" and unlisted["status"] == 403
    assert anonymous["correlation_id"]


def test_server_error_is_recorded_as_error(
    setup: tuple[TestClient, InMemorySpanExporter], caplog: pytest.LogCaptureFixture
) -> None:
    client, exporter = setup
    with caplog.at_level(logging.INFO, logger="app.access"):
        assert client.get("/api/boom", headers={"x-user": "ana@x.test"}).status_code == 500
    assert last_log(caplog)["result"] == "error"
    assert exporter.get_finished_spans()[-1].attributes["app.result"] == "error"  # type: ignore[index]


def test_well_formed_incoming_correlation_id_is_kept_and_garbage_replaced(
    setup: tuple[TestClient, InMemorySpanExporter],
) -> None:
    client, _ = setup
    kept = client.get(
        "/api/ok", headers={"x-user": "ana@x.test", "x-correlation-id": "req-12345678"}
    )
    assert kept.headers["x-correlation-id"] == "req-12345678"
    bad = client.get("/api/ok", headers={"x-user": "ana@x.test", "x-correlation-id": "a b\nc"})
    assert bad.headers["x-correlation-id"] != "a b\nc"
    assert new_correlation_id(None) != new_correlation_id(None)


@pytest.mark.parametrize(
    "secret",
    [
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq",
        "https://a.blob.core.windows.net/uploads/x?sv=1&sp=c&sig=SuperSecretSignature123",
        "postgresql+psycopg://user:hunter2@db:5432/app",
        "Authorization: Bearer abc.def.ghi",
        "x-ms-client-principal: eyJhdXRoX3R5cCI6Imdvb2dsZSJ9",
        "Password=s3cr3t;Server=x",
    ],
)
def test_redaction_removes_secret_values(secret: str) -> None:
    cleaned = redact(f"event {secret} end")
    for leaked in (
        "Eby8vdM0",
        "SuperSecretSignature123",
        "hunter2",
        "abc.def.ghi",
        "eyJhdXRo",
        "s3cr3t",
    ):
        assert leaked not in cleaned
    assert "[REDACTED]" in cleaned


def test_log_filter_redacts_any_logger_output(caplog: pytest.LogCaptureFixture) -> None:
    log = logging.getLogger("some.library")
    flt = SecretRedactionFilter()
    record = log.makeRecord(
        "some.library", logging.INFO, "f", 1, "conn %s", ("Password=hunter2",), None
    )
    flt.filter(record)
    assert "hunter2" not in record.getMessage()


def test_non_secret_text_is_untouched() -> None:
    assert redact("GET /api/technical/me 200") == "GET /api/technical/me 200"
