"""Composition root: picks adapters from settings. Business modules never read the environment."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.services.ports import IdentityProvider, MailTransport, StorageService, TelemetryExporter
from app.settings import Settings, StartupError


@dataclass
class AdapterRegistry:
    """Factories keyed by the configured adapter name."""

    identity: Mapping[str, Callable[[Settings], IdentityProvider]] = field(default_factory=dict)
    storage: Mapping[str, Callable[[Settings], StorageService]] = field(default_factory=dict)
    mail: Mapping[str, Callable[[Settings], MailTransport]] = field(default_factory=dict)
    telemetry: Mapping[str, Callable[[Settings], TelemetryExporter]] = field(default_factory=dict)


def _pick(
    kind: str, name: str, factories: Mapping[str, Callable[[Settings], Any]]
) -> Callable[[Settings], Any]:
    try:
        return factories[name]
    except KeyError:
        raise StartupError(f"No {kind} adapter is registered for '{name}'") from None


class Container:
    """Resolves each adapter lazily, so a process only needs the adapters it uses."""

    def __init__(self, settings: Settings, registry: AdapterRegistry) -> None:
        self.settings = settings
        self._registry = registry
        self._cache: dict[str, Any] = {}

    def _get(self, kind: str, name: str, factories: Mapping[str, Callable[[Settings], Any]]) -> Any:
        if kind not in self._cache:
            self._cache[kind] = _pick(kind, name, factories)(self.settings)
        return self._cache[kind]

    def identity(self) -> IdentityProvider:
        return self._get("identity", self.settings.identity_provider, self._registry.identity)  # type: ignore[no-any-return]

    def storage(self) -> StorageService:
        return self._get("storage", self.settings.storage_backend, self._registry.storage)  # type: ignore[no-any-return]

    def mail(self) -> MailTransport:
        return self._get("mail", self.settings.mail_transport, self._registry.mail)  # type: ignore[no-any-return]

    def telemetry(self) -> TelemetryExporter:
        return self._get("telemetry", self.settings.telemetry_exporter, self._registry.telemetry)  # type: ignore[no-any-return]
