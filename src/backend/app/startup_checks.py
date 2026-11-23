"""Checks that stop a process from starting with a configuration that cannot work."""

from sqlalchemy import Engine

from app.adapters.db.catalog import branch_names
from app.settings import Settings, StartupError


def require_catalog(engine: Engine, settings: Settings) -> None:
    """Imports need the branch catalog (RF-06): without it every given branch would be an error."""
    if settings.imports_enabled and not branch_names(engine):
        raise StartupError(
            "IMPORTS_ENABLED is true but the branch catalog is empty: set BRANCH_CATALOG and run "
            "`python -m app.seed_catalog` (the real branch names come from the administrator)"
        )
