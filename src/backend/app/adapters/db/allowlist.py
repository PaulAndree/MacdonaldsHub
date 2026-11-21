from typing import cast

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from app.adapters.db.models import AllowlistEntry
from app.domain.roles import Role
from app.services.ports import AllowlistRecord


class SqlAllowlistRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_active(self, identifier: str) -> AllowlistRecord | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(AllowlistEntry).where(
                    AllowlistEntry.identifier == identifier, AllowlistEntry.active.is_(True)
                )
            )
            if row is None:
                return None
            return AllowlistRecord(identifier=row.identifier, role=cast(Role, row.role))


def seed_initial_admin(engine: Engine, identifier: str, email: str | None = None) -> None:
    """Idempotently allow the initial administrator; the value comes from configuration."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role, active) "
                "VALUES (gen_random_uuid(), :identifier, :email, 'administrator', true) "
                "ON CONFLICT (identifier) DO UPDATE SET role = 'administrator', active = true"
            ),
            {"identifier": identifier, "email": email},
        )
