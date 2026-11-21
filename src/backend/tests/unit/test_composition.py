from typing import Any

import pytest

from app.composition import AdapterRegistry, Container
from app.settings import Settings, StartupError

ENV: dict[str, Any] = {
    "app_env": "local",
    "identity_provider": "dev",
    "dev_identity_email": "d@x.test",
    "storage_backend": "azurite",
    "storage_connection_string": "UseDevelopmentStorage=true",
    "mail_transport": "smtp_capture",
    "telemetry_exporter": "console",
    "database_url": "postgresql+psycopg://u:p@h/db",
    "frontend_origin": "http://localhost:3000",
}


def settings(**over: Any) -> Settings:
    return Settings(_env_file=None, **{**ENV, **over})


class Tag:
    def __init__(self, name: str) -> None:
        self.name = name


def registry() -> AdapterRegistry:
    def f(n: str) -> Any:
        return lambda _s: Tag(n)

    return AdapterRegistry(
        identity={"dev": f("identity:dev"), "easy_auth": f("identity:easy_auth")},
        storage={"azurite": f("storage:azurite"), "azure_blob": f("storage:azure_blob")},
        mail={"smtp_capture": f("mail:capture"), "smtp": f("mail:smtp")},
        telemetry={"console": f("tel:console"), "azure_monitor": f("tel:azure")},
    )


def test_local_selection() -> None:
    c = Container(settings(), registry())
    assert c.identity().name == "identity:dev"  # type: ignore[attr-defined]
    assert c.storage().name == "storage:azurite"  # type: ignore[attr-defined]
    assert c.mail().name == "mail:capture"  # type: ignore[attr-defined]
    assert c.telemetry().name == "tel:console"  # type: ignore[attr-defined]


def test_azure_selection_uses_same_container_with_different_adapters() -> None:
    s = settings(
        app_env="production",
        database_auth="managed_identity",
        identity_provider="easy_auth",
        allowlist_identifier="email",
        initial_admin_email="admin@example.test",
        storage_backend="azure_blob",
        storage_account_url="https://a.blob.core.windows.net",
        storage_connection_string=None,
        mail_transport="smtp",
        telemetry_exporter="azure_monitor",
        applicationinsights_connection_string="InstrumentationKey=00000000-0000-0000-0000-000000000000",
    )
    c = Container(s, registry())
    assert c.identity().name == "identity:easy_auth"  # type: ignore[attr-defined]
    assert c.storage().name == "storage:azure_blob"  # type: ignore[attr-defined]
    assert c.mail().name == "mail:smtp"  # type: ignore[attr-defined]
    assert c.telemetry().name == "tel:azure"  # type: ignore[attr-defined]


def test_adapter_is_built_once() -> None:
    c = Container(settings(), registry())
    assert c.storage() is c.storage()


def test_unregistered_adapter_fails_with_clear_error() -> None:
    c = Container(settings(), AdapterRegistry())
    with pytest.raises(StartupError, match="No storage adapter is registered for 'azurite'"):
        c.storage()


def test_only_requested_adapters_are_resolved() -> None:
    reg = registry()
    reg.mail = {}  # mail adapter does not exist yet in this change
    c = Container(settings(), reg)
    assert c.identity() is not None  # not affected by the missing mail adapter
