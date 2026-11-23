"""Default adapter registry. Each adapter module registers its factory here as it is implemented."""

from app.adapters.identity.dev import DevIdentityProvider
from app.adapters.identity.easy_auth import EasyAuthIdentityProvider
from app.adapters.mail.smtp import SmtpMailTransport
from app.adapters.storage.factories import azure_blob_storage, azurite_storage
from app.adapters.telemetry.exporters import AzureMonitorExporter, ConsoleExporter
from app.composition import AdapterRegistry
from app.services.ports import IdentityProvider, MailTransport, TelemetryExporter
from app.settings import Settings


def _dev_identity(settings: Settings) -> IdentityProvider:
    assert settings.dev_identity_email is not None  # guaranteed by Settings validation
    return DevIdentityProvider(settings.dev_identity_email, settings.dev_identity_role)


def _easy_auth_identity(settings: Settings) -> IdentityProvider:
    return EasyAuthIdentityProvider()


def _smtp_capture(settings: Settings) -> MailTransport:
    """Local capture service: no TLS and no login, and it relays nothing."""
    assert settings.smtp_host is not None  # sending is unavailable without a host
    return SmtpMailTransport(settings.smtp_host, settings.smtp_port or 1025, None, None, False)


def _smtp(settings: Settings) -> MailTransport:
    """The institutional mailbox, with the password from the secret store."""
    assert settings.smtp_host is not None
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    return SmtpMailTransport(
        settings.smtp_host,
        settings.smtp_port or 587,
        settings.smtp_user,
        password,
        settings.smtp_starttls,
    )


def _console_telemetry(settings: Settings) -> TelemetryExporter:
    return ConsoleExporter()


def _azure_monitor_telemetry(settings: Settings) -> TelemetryExporter:
    assert settings.applicationinsights_connection_string is not None  # validated in Settings
    return AzureMonitorExporter(settings.applicationinsights_connection_string.get_secret_value())


def default_registry() -> AdapterRegistry:
    return AdapterRegistry(
        identity={"dev": _dev_identity, "easy_auth": _easy_auth_identity},
        storage={"azurite": azurite_storage, "azure_blob": azure_blob_storage},
        mail={"smtp_capture": _smtp_capture, "smtp": _smtp},
        telemetry={"console": _console_telemetry, "azure_monitor": _azure_monitor_telemetry},
    )
