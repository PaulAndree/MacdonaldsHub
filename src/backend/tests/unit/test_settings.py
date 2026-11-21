import pytest
from pydantic import ValidationError

from app.settings import Settings, StartupError, load_settings_or_exit

BASE = {
    "APP_ENV": "local",
    "IDENTITY_PROVIDER": "dev",
    "DEV_IDENTITY_EMAIL": "dev@example.test",
    "DEV_IDENTITY_ROLE": "administrator",
    "STORAGE_BACKEND": "azurite",
    "STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",
    "MAIL_TRANSPORT": "smtp_capture",
    "TELEMETRY_EXPORTER": "console",
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/db",
    "FRONTEND_ORIGIN": "http://localhost:3000",
}


def make(env: dict[str, str]) -> Settings:
    return Settings(_env_file=None, **{k.lower(): v for k, v in env.items()})  # type: ignore[arg-type]


def test_valid_local_settings_load() -> None:
    s = make(BASE)
    assert s.app_env == "local"
    assert s.dev_identity_role == "administrator"


@pytest.mark.parametrize(
    "missing", ["APP_ENV", "IDENTITY_PROVIDER", "DATABASE_URL", "STORAGE_BACKEND"]
)
def test_missing_required_value_fails(missing: str) -> None:
    env = {k: v for k, v in BASE.items() if k != missing}
    with pytest.raises(ValidationError):
        make(env)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("APP_ENV", "staging"),
        ("IDENTITY_PROVIDER", "password"),
        ("STORAGE_BACKEND", "s3"),
        ("DEV_IDENTITY_ROLE", "root"),
        ("TELEMETRY_EXPORTER", "datadog"),
    ],
)
def test_invalid_value_fails(key: str, value: str) -> None:
    with pytest.raises(ValidationError):
        make({**BASE, key: value})


def test_secrets_are_not_printed() -> None:
    s = make(BASE)
    assert "u:p@" not in repr(s)
    assert "UseDevelopmentStorage" not in repr(s)


@pytest.mark.parametrize("env_name", ["test", "production"])
def test_dev_identity_rejected_outside_local(env_name: str) -> None:
    env = {
        **BASE,
        "APP_ENV": env_name,
        "STORAGE_BACKEND": "azure_blob",
        "STORAGE_ACCOUNT_URL": "https://x.blob.core.windows.net",
        "TELEMETRY_EXPORTER": "azure_monitor",
    }
    with pytest.raises(
        ValidationError, match="IDENTITY_PROVIDER=dev is only allowed when APP_ENV=local"
    ):
        make(env)


@pytest.mark.parametrize("env_name", ["test", "production"])
def test_startup_exits_with_clear_error_for_dev_identity_in_azure(
    env_name: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for k in list(BASE):
        monkeypatch.delenv(k, raising=False)
    for k, v in {**BASE, "APP_ENV": env_name}.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(SystemExit) as exc:
        load_settings_or_exit()
    assert exc.value.code != 0
    assert "IDENTITY_PROVIDER=dev is only allowed when APP_ENV=local" in capsys.readouterr().err


def test_easyauth_identity_in_production_is_accepted() -> None:
    env = {k: v for k, v in BASE.items() if not k.startswith("DEV_")}
    env.update(
        ALLOWLIST_IDENTIFIER="email",
        INITIAL_ADMIN_EMAIL="admin@example.test",
        APP_ENV="production",
        DATABASE_AUTH="managed_identity",
        IDENTITY_PROVIDER="easy_auth",
        STORAGE_BACKEND="azure_blob",
        STORAGE_ACCOUNT_URL="https://x.blob.core.windows.net",
        TELEMETRY_EXPORTER="azure_monitor",
        APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    assert make(env).identity_provider == "easy_auth"


def test_azure_blob_requires_account_url() -> None:
    env = {**BASE, "STORAGE_BACKEND": "azure_blob"}
    env.pop("STORAGE_CONNECTION_STRING")
    with pytest.raises(ValidationError, match="STORAGE_ACCOUNT_URL"):
        make(env)


def test_startup_error_is_exposed() -> None:
    assert issubclass(StartupError, Exception)


FAKE_APPINSIGHTS = "InstrumentationKey=00000000-0000-0000-0000-000000000000"
AZURE = {
    "APP_ENV": "production",
    "DATABASE_AUTH": "managed_identity",
    "IDENTITY_PROVIDER": "easy_auth",
    "STORAGE_BACKEND": "azure_blob",
    "STORAGE_ACCOUNT_URL": "https://x.blob.core.windows.net",
    "TELEMETRY_EXPORTER": "azure_monitor",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": FAKE_APPINSIGHTS,
}


def azure_env(**over: str) -> dict[str, str]:
    env = {k: v for k, v in BASE.items() if not k.startswith(("DEV_", "STORAGE_CONN"))}
    return {**env, **AZURE, **over}


def test_easy_auth_requires_allowlist_identifier_decision() -> None:  # P-07, no default
    with pytest.raises(ValidationError, match="ALLOWLIST_IDENTIFIER"):
        make(azure_env(INITIAL_ADMIN_EMAIL="a@x.test"))


def test_easy_auth_requires_initial_admin_matching_identifier_kind() -> None:
    with pytest.raises(ValidationError, match="INITIAL_ADMIN"):
        make(azure_env(ALLOWLIST_IDENTIFIER="sub", INITIAL_ADMIN_EMAIL="a@x.test"))
    s = make(azure_env(ALLOWLIST_IDENTIFIER="sub", INITIAL_ADMIN_SUBJECT="g-1"))
    assert s.initial_admin_identifier == "g-1"


def test_easy_auth_is_rejected_locally() -> None:
    env = {
        **BASE,
        "IDENTITY_PROVIDER": "easy_auth",
        "ALLOWLIST_IDENTIFIER": "email",
        "INITIAL_ADMIN_EMAIL": "a@x.test",
    }
    with pytest.raises(ValidationError, match="not allowed when APP_ENV=local"):
        make(env)


def test_azure_monitor_requires_connection_string() -> None:
    env = azure_env(ALLOWLIST_IDENTIFIER="email", INITIAL_ADMIN_EMAIL="a@x.test")
    env.pop("APPLICATIONINSIGHTS_CONNECTION_STRING")
    with pytest.raises(ValidationError, match="APPLICATIONINSIGHTS_CONNECTION_STRING"):
        make(env)


@pytest.mark.parametrize("env_name", ["test", "production"])
def test_password_database_auth_is_rejected_outside_local(env_name: str) -> None:
    env = azure_env(ALLOWLIST_IDENTIFIER="email", INITIAL_ADMIN_EMAIL="a@x.test", APP_ENV=env_name)
    env["DATABASE_AUTH"] = "password"
    with pytest.raises(ValidationError, match="DATABASE_AUTH=managed_identity is required"):
        make(env)


def test_password_database_auth_is_fine_locally() -> None:
    assert make(BASE).database_auth == "password"
