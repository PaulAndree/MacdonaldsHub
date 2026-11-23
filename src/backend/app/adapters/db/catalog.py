"""Branch catalog in PostgreSQL. The values come from configuration (P-01), never from the code."""

from collections.abc import Sequence

from sqlalchemy import Engine, text


def seed_branches(engine: Engine, names: Sequence[str], deactivate_missing: bool = False) -> None:
    """Idempotently load the configured branches. A branch is never deleted (incidents use it);
    with `deactivate_missing`, one no longer configured is deactivated instead."""
    with engine.begin() as conn:
        for name in names:
            conn.execute(
                text(
                    "INSERT INTO branch (name, active) VALUES (:name, true) "
                    "ON CONFLICT (name) DO UPDATE SET active = true"
                ),
                {"name": name},
            )
        if deactivate_missing:
            conn.execute(
                text("UPDATE branch SET active = false WHERE NOT (name = ANY(:names))"),
                {"names": list(names)},
            )


def branch_names(engine: Engine) -> list[str]:
    """The active branches, which are the ones an imported row may name."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM branch WHERE active ORDER BY name"))
        return [row[0] for row in rows]
