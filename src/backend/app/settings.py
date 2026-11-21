"""Typed, fail-fast configuration. The only place environment variables are read.

Configuration selects adapters, never business rules (RNF-15).
"""

import sys
from typing import Literal, Self

from pydantic import SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.roles import Role

AppEnv = Literal["local", "test", "production"]


class StartupError(Exception):
    """Configuration is invalid; the process must not start."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_env: AppEnv
    database_url: SecretStr
    # Outside local the database has no password: the app's managed identity gets tokens (ADR-15).
    database_auth: Literal["password", "managed_identity"] = "password"
    frontend_origin: str

    identity_provider: Literal["dev", "easy_auth"]
    dev_identity_email: str | None = None
    dev_identity_role: Role = "administrator"
    initial_admin_email: str | None = None
    initial_admin_subject: str | None = None
    # P-07 is pending: which stable identifier the allowlist uses. No default on purpose.
    allowlist_identifier: Literal["sub", "email"] | None = None

    storage_backend: Literal["azurite", "azure_blob"]
    storage_connection_string: SecretStr | None = None
    storage_account_url: str | None = None
    # Browser-reachable base URL for upload grants when it differs from the internal one
    # (local Compose: the API reaches Azurite as http://azurite:10000, the browser as 127.0.0.1).
    storage_public_endpoint: str | None = None

    mail_transport: Literal["smtp_capture", "smtp"]
    smtp_host: str | None = None
    smtp_port: int | None = None

    telemetry_exporter: Literal["console", "azure_monitor"]
    applicationinsights_connection_string: SecretStr | None = None

    @property
    def initial_admin_identifier(self) -> str | None:
        if self.allowlist_identifier == "sub":
            return self.initial_admin_subject
        if self.allowlist_identifier == "email":
            return self.initial_admin_email
        return None

    @model_validator(mode="after")
    def _validate_combinations(self) -> Self:
        # RNF-16 / BASE-08: the development identity can never run outside local.
        if self.identity_provider == "dev" and self.app_env != "local":
            raise ValueError("IDENTITY_PROVIDER=dev is only allowed when APP_ENV=local")
        if self.identity_provider == "dev" and not self.dev_identity_email:
            raise ValueError("DEV_IDENTITY_EMAIL is required when IDENTITY_PROVIDER=dev")
        if self.app_env != "local" and self.database_auth != "managed_identity":
            raise ValueError("DATABASE_AUTH=managed_identity is required when APP_ENV is not local")
        if self.identity_provider == "easy_auth":
            if self.app_env == "local":
                raise ValueError("IDENTITY_PROVIDER=easy_auth is not allowed when APP_ENV=local")
            if self.allowlist_identifier is None:
                raise ValueError("ALLOWLIST_IDENTIFIER (sub or email) is required (decision P-07)")
            if self.initial_admin_identifier is None:
                raise ValueError(
                    "INITIAL_ADMIN_SUBJECT or INITIAL_ADMIN_EMAIL (matching "
                    "ALLOWLIST_IDENTIFIER) is required"
                )
        if (
            self.telemetry_exporter == "azure_monitor"
            and not self.applicationinsights_connection_string
        ):
            raise ValueError(
                "APPLICATIONINSIGHTS_CONNECTION_STRING is required "
                "when TELEMETRY_EXPORTER=azure_monitor"
            )
        if self.storage_backend == "azure_blob" and not self.storage_account_url:
            raise ValueError("STORAGE_ACCOUNT_URL is required when STORAGE_BACKEND=azure_blob")
        if self.storage_backend == "azurite" and self.storage_connection_string is None:
            raise ValueError("STORAGE_CONNECTION_STRING is required when STORAGE_BACKEND=azurite")
        return self


def load_settings_or_exit() -> Settings:
    """Load settings; on any problem print a clear message and exit non-zero."""
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        details = "; ".join(
            err["msg"].removeprefix("Value error, ")
            if err["loc"] == ()
            else f"{'.'.join(str(p).upper() for p in err['loc'])}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
        )
        print(f"Startup refused: invalid configuration: {details}", file=sys.stderr)
        raise SystemExit(2) from None


class DatabaseSettings(BaseSettings):
    """Only what database tooling (migrations) needs, so it does not require unrelated config."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    database_url: SecretStr
    database_auth: Literal["password", "managed_identity"] = "password"
