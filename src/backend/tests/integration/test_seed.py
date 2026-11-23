"""The seed command loads the administrator and the branch catalog from configuration."""

import pytest
from sqlalchemy import text

from app.adapters.db.catalog import branch_names
from app.adapters.db.engine import make_engine
from app.migrate import run as migrate
from app.seed import run
from tests.unit.test_settings import BASE, make

pytestmark = pytest.mark.integration

REAL = "Palacio de hielo, Hortaleza, Plaza, Bravo, Manoteras, Plenilunio, Ermita"


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    migrate("upgrade", database_url)
    yield eng
    eng.dispose()


def test_the_catalog_of_the_administrator_is_loaded_in_lowercase(engine) -> None:  # type: ignore[no-untyped-def]
    run(make({**BASE, "BRANCH_CATALOG": REAL}), engine)
    assert branch_names(engine) == sorted(
        ["palacio de hielo", "hortaleza", "plaza", "bravo", "manoteras", "plenilunio", "ermita"]
    )


def test_seeding_twice_changes_nothing(engine) -> None:  # type: ignore[no-untyped-def]
    settings = make({**BASE, "BRANCH_CATALOG": REAL})
    run(settings, engine)
    run(settings, engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM branch")).scalar() == 7


def test_without_configuration_nothing_is_invented(engine) -> None:  # type: ignore[no-untyped-def]
    run(make(BASE), engine)
    assert branch_names(engine) == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM allowlist_entry")).scalar() == 0
