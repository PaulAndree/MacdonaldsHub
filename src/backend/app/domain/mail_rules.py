"""Rules of the sender (RN-05, RN-08, ADR-09). Pure rules, no I/O."""

from datetime import datetime, timedelta

# At least this long between the start of two consecutive attempts, whatever their result. It is a
# constant on purpose: it is a business rule (ADR-09), not a setting.
MIN_INTERVAL_SECONDS = 30


def unavailable_reason(
    app_env: str,
    smtp_host: str | None,
    smtp_from: str | None,
    test_recipient: str | None,
) -> str | None:
    """Why the sender cannot start attempts, or None when it can.

    Unavailability is not an error: the emails stay pending. Production never sends while no real
    recipient is defined (P-01).
    """
    if app_env == "production":
        return (
            "El envío está desactivado en producción mientras no haya destinatarios reales "
            "definidos."
        )
    if not smtp_host:
        return "No hay un servidor de correo configurado."
    if not smtp_from:
        return "No hay un remitente configurado."
    if not test_recipient:
        return "No hay un destinatario de prueba configurado."
    return None


def next_eligible_at(paused: bool, last_started_at: datetime | None) -> datetime | None:
    """The earliest time the next attempt may start, or None when it is paused or nothing has
    started yet (so it can start at once)."""
    if paused or last_started_at is None:
        return None
    return last_started_at + timedelta(seconds=MIN_INTERVAL_SECONDS)


def can_start(paused: bool, last_started_at: datetime | None, now: datetime) -> bool:
    """A paused queue starts nothing; otherwise at least 30 seconds after the previous start,
    whatever its result. The interval counts from the start of an attempt, not from its end."""
    if paused:
        return False
    return last_started_at is None or now >= last_started_at + timedelta(
        seconds=MIN_INTERVAL_SECONDS
    )


def recipient_authorized(stored: str, configured: str | None) -> bool:
    """Only the configured test recipient may receive an email. Real providers never do (P-01)."""
    return bool(configured) and stored.lower() == (configured or "").lower()
