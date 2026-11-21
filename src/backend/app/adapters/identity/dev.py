"""Local development identity. Only constructible when APP_ENV=local (see Settings guard)."""

from app.domain.roles import Role
from app.services.ports import Identity


class DevIdentityProvider:
    def __init__(self, email: str, role: Role) -> None:
        self._identity = Identity(subject=email, email=email, preauthorized_role=role)

    def resolve(self, headers: dict[str, str]) -> Identity | None:
        # Identity headers sent by the caller are deliberately ignored here.
        return self._identity
