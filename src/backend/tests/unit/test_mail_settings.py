"""Mail settings and availability (RN-08, P-02): nothing sends until it is configured and safe."""

import pytest

from app.domain.mail_rules import unavailable_reason
from tests.unit.test_settings import BASE, make

FULL = {
    "MAIL_TRANSPORT": "smtp",
    "SMTP_HOST": "smtp.example.test",
    "SMTP_PORT": "587",
    "SMTP_USER": "sender@example.test",
    "SMTP_PASSWORD": "s3cr3t-value",
    "SMTP_FROM": "institutional@example.test",
    "SMTP_STARTTLS": "true",
    "TEST_RECIPIENT_EMAIL": "test-recipient@example.test",
}


def test_the_mail_settings_load() -> None:
    s = make({**BASE, **FULL})
    assert (s.smtp_host, s.smtp_port, s.smtp_user) == (
        "smtp.example.test",
        587,
        "sender@example.test",
    )
    assert s.smtp_from == "institutional@example.test" and s.smtp_starttls is True


def test_the_password_never_shows_in_a_representation_or_a_message() -> None:
    s = make({**BASE, **FULL})
    for text in (repr(s), str(s), repr(s.smtp_password), str(s.smtp_password), s.model_dump_json()):
        assert "s3cr3t-value" not in text
    assert s.smtp_password is not None and s.smtp_password.get_secret_value() == "s3cr3t-value"


def test_the_mail_settings_are_optional_so_an_environment_can_start_without_them() -> None:
    s = make(BASE)
    assert (s.smtp_host, s.smtp_user, s.smtp_password, s.smtp_from) == (None, None, None, None)
    assert s.smtp_starttls is False


# --- when sending is available -----------------------------------------------------------------------------


def reason(**over) -> str | None:  # type: ignore[no-untyped-def]
    base = dict(
        app_env="test",
        smtp_host="smtp.example.test",
        smtp_from="institutional@example.test",
        test_recipient="test-recipient@example.test",
    )
    return unavailable_reason(**{**base, **over})


def test_a_configured_test_environment_can_send() -> None:
    assert reason() is None
    assert reason(app_env="local", smtp_host="mailpit") is None


@pytest.mark.parametrize(
    ("over", "word"),
    [
        ({"smtp_host": None}, "servidor de correo"),
        ({"smtp_host": ""}, "servidor de correo"),
        ({"smtp_from": None}, "remitente"),
        ({"test_recipient": None}, "destinatario"),
        ({"test_recipient": ""}, "destinatario"),
        ({"app_env": "production"}, "producción"),
    ],
)
def test_each_missing_piece_makes_sending_unavailable_and_says_why(over: dict, word: str) -> None:  # type: ignore[type-arg]
    message = reason(**over)
    assert message is not None and word in message


def test_production_is_unavailable_even_when_everything_else_is_configured() -> None:
    # No real recipient is defined (P-01): production never sends.
    assert reason(app_env="production") is not None
