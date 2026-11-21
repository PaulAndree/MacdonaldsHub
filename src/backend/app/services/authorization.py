"""Authorization: an authenticated identity must be on the allowlist (RNF-04)."""

from dataclasses import dataclass
from typing import Literal

from app.domain.roles import Role
from app.services.ports import AllowlistRepository, Identity


@dataclass(frozen=True)
class AuthorizedUser:
    identifier: str
    email: str | None
    role: Role


class Authorizer:
    """Matches an identity to the allowlist using the configured stable identifier (P-07)."""

    def __init__(self, repo: AllowlistRepository, key: Literal["sub", "email"] | None) -> None:
        self._repo = repo
        self._key = key

    def authorize(self, identity: Identity) -> AuthorizedUser | None:
        if identity.preauthorized_role is not None:
            who = identity.email or identity.subject or "dev"
            return AuthorizedUser(
                identifier=who, email=identity.email, role=identity.preauthorized_role
            )
        value = (
            identity.subject
            if self._key == "sub"
            else identity.email
            if self._key == "email"
            else None
        )
        if not value:
            return None
        record = self._repo.find_active(value)
        if record is None:
            return None
        return AuthorizedUser(identifier=record.identifier, email=identity.email, role=record.role)
