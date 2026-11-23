"""Shared helpers of the sender tests: emails in the outbox, a controllable transport."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine, text

from app.services.ports import MailRefused, MailUnverified, OutgoingEmail

TEST_RECIPIENT = "test-recipient@example.test"


def add_email(
    engine: Engine,
    order_id: str,
    provider: str = "uber eats",
    batch: str | None = "new",
    recipient: str = TEST_RECIPIENT,
    seconds_old: int = 0,
) -> dict[str, str | None]:
    """A confirmed batch (unless `batch` is None or an existing id) with one pending email."""
    with engine.begin() as conn:
        batch_id: str | None
        if batch == "new":
            batch_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO batch (id, owner, state, file_name, size_bytes, blob_name) "
                    "VALUES (:id, 'ana', 'confirmed', 'f.xlsx', 1, :blob)"
                ),
                {"id": batch_id, "blob": f"batches/{batch_id}.xlsx"},
            )
        else:
            batch_id = batch
        incident = conn.execute(
            text(
                "INSERT INTO incident (provider, order_id, incident_date, state, batch_id, source, "
                "created_by) VALUES (:p, :o, '2026-11-20', 'pending_send', :b, 'import', 'ana') "
                "RETURNING id::text"
            ),
            {"p": provider, "o": order_id, "b": batch_id},
        ).scalar()
        email = conn.execute(
            text(
                "INSERT INTO outbox (incident_id, batch_id, state, recipient, template_version, "
                "subject, body, created_at) VALUES (:i, :b, 'pending', :r, 'example-1', "
                "'Reclamación de incidente', 'Incidente {orderId} para su reclamación.', "
                "now() - make_interval(secs => :age)) RETURNING id::text"
            ),
            {"i": incident, "b": batch_id, "r": recipient, "age": seconds_old},
        ).scalar()
    return {"email": email, "incident": incident, "batch": batch_id}


def resume(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE mail_control SET paused = false, paused_at = NULL"))


def pause(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("UPDATE mail_control SET paused = true, paused_at = now()"))


def age_last_start(engine: Engine, seconds: float | None) -> None:
    """Pretend the last attempt started `seconds` ago (None: never)."""
    with engine.begin() as conn:
        if seconds is None:
            conn.execute(text("UPDATE mail_control SET last_started_at = NULL"))
        else:
            conn.execute(
                text("UPDATE mail_control SET last_started_at = now() - make_interval(secs => :s)"),
                {"s": seconds},
            )


def row(engine: Engine, sql: str, **params: Any) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).one()


@dataclass
class FakeTransport:
    """Counts the calls and can be told what to do."""

    outcome: Exception | None = None
    sent: list[OutgoingEmail] = field(default_factory=list)
    on_send: Any = None

    def send(self, email: OutgoingEmail) -> None:
        self.sent.append(email)
        if self.on_send:
            self.on_send(email)
        if self.outcome is not None:
            raise self.outcome


REFUSED = MailRefused("El servidor rechazó el destinatario: 550 no existe")
UNVERIFIED = MailUnverified("El envío se interrumpió y no se pudo verificar el resultado.")
