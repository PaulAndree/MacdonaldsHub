"""Explicit migration command: `python -m app.migrate upgrade|downgrade|current [target]`.

Migrations are never applied implicitly at API or worker start (they would race).
"""

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from app.adapters.db.engine import DatabaseAuth
from app.settings import DatabaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(database_url: str, database_auth: DatabaseAuth = "password") -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_auth"] = database_auth
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def run(
    action: str,
    database_url: str,
    target: str | None = None,
    database_auth: DatabaseAuth = "password",
) -> None:
    cfg = alembic_config(database_url, database_auth)
    if action == "upgrade":
        command.upgrade(cfg, target or "head")
    elif action == "downgrade":
        command.downgrade(cfg, target or "-1")
    elif action == "current":
        command.current(cfg)
    else:
        raise SystemExit(f"Unknown action '{action}'. Use upgrade, downgrade or current.")


def main(argv: list[str]) -> None:
    if not argv:
        raise SystemExit("Usage: python -m app.migrate upgrade|downgrade|current [target]")
    try:
        db = DatabaseSettings()  # type: ignore[call-arg]
    except ValidationError:
        raise SystemExit("Startup refused: DATABASE_URL is required") from None
    run(
        argv[0],
        db.database_url.get_secret_value(),
        argv[1] if len(argv) > 1 else None,
        db.database_auth,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
