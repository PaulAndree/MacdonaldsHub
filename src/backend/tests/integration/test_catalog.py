"""The branch catalog is loaded from configuration, and imports need it (RF-06, P-01)."""

import pytest
from sqlalchemy import text

from app.adapters.db.catalog import branch_names, seed_branches
from app.adapters.db.engine import make_engine
from app.migrate import run
from app.settings import StartupError
from app.startup_checks import require_catalog
from tests.unit.test_settings import BASE, make

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def test_seeding_is_idempotent_and_keeps_existing_branches(engine) -> None:  # type: ignore[no-untyped-def]
    seed_branches(engine, ("centro", "norte"))
    seed_branches(engine, ("norte", "sur"))
    assert branch_names(engine) == ["centro", "norte", "sur"]


def test_a_branch_removed_from_configuration_is_deactivated_not_deleted(engine) -> None:  # type: ignore[no-untyped-def]
    # Incidents may reference it, so it is never deleted.
    seed_branches(engine, ("centro", "norte"))
    seed_branches(engine, ("centro",), deactivate_missing=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name, active FROM branch ORDER BY name")).all()
    assert rows == [("centro", True), ("norte", False)]
    assert branch_names(engine) == ["centro"]


def test_startup_is_refused_when_imports_are_enabled_and_the_catalog_is_empty(engine) -> None:  # type: ignore[no-untyped-def]
    settings = make({**BASE, "IMPORTS_ENABLED": "true"})
    with pytest.raises(StartupError, match="BRANCH_CATALOG"):
        require_catalog(engine, settings)


def test_startup_passes_when_imports_are_enabled_and_the_catalog_is_loaded(engine) -> None:  # type: ignore[no-untyped-def]
    seed_branches(engine, ("centro",))
    require_catalog(engine, make({**BASE, "IMPORTS_ENABLED": "true"}))


def test_startup_does_not_need_a_catalog_while_imports_are_disabled(engine) -> None:  # type: ignore[no-untyped-def]
    require_catalog(engine, make(BASE))
