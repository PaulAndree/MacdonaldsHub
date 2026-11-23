"""Shared helpers of the batch integration tests: uploading, preparing and inspecting a batch."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from app.adapters.db.preparation import SqlPreparationRepository
from app.services.preparation import PreparationService
from tests.integration.test_api import principal_headers

ADMIN = "admin@example.test"
SAMPLES = Path(__file__).resolve().parents[4] / "docs" / "samples" / "xlsx"
ROW = [("s", "uber eats"), ("s", "UE-1"), ("s", "2026-11-02 12:15")]


def service(client: Any, now: datetime | None = None) -> PreparationService:
    return PreparationService(
        SqlPreparationRepository(client.engine),
        client.app.state.container.storage(),
        clock=(lambda: now) if now else (lambda: datetime.now(UTC)),
    )


def upload(client: Any, content: bytes, who: str = ADMIN, complete: bool = True) -> str:
    """Registers a batch, stores the file as the browser would, and asks for processing."""
    created = client.post(
        "/api/batches",
        json={"fileName": "f.xlsx", "sizeBytes": len(content)},
        headers=principal_headers(who),
    ).json()
    grant = created["upload"]
    assert (
        httpx.request(
            grant["method"], grant["url"], content=content, headers=grant["headers"]
        ).status_code
        == 201
    )
    batch_id = created["batch"]["id"]
    if complete:
        done = client.post(f"/api/batches/{batch_id}/uploaded", headers=principal_headers(who))
        assert done.status_code == 202
    return batch_id  # type: ignore[no-any-return]


def state(client: Any, batch_id: str) -> dict[str, Any]:
    return client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()  # type: ignore[no-any-return]


def staged(client: Any, batch_id: str) -> list[tuple[int, str, str | None]]:
    with client.engine.connect() as conn:
        return [
            tuple(r)
            for r in conn.execute(
                text(
                    "SELECT row_number, class, reason FROM batch_row "
                    "WHERE batch_id = :b ORDER BY row_number"
                ),
                {"b": batch_id},
            )
        ]  # type: ignore[misc]


def no_definitive_records(client: Any) -> None:
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM outbox")).scalar() == 0


def seed_incident(client: Any, order_id: str = "UE-1", claim: str | None = None) -> None:
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO incident (provider, order_id, incident_date, incident_time, state, "
                "source, created_by, claim_amount) VALUES ('uber eats', :o, '2026-11-02', '12:15', "
                "'imported_no_email', 'import', 'seed', :c)"
            ),
            {"o": order_id, "c": claim},
        )
