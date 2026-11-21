import pytest
from sqlalchemy import text

from app.adapters.db.allowlist import SqlAllowlistRepository, seed_initial_admin
from app.adapters.db.engine import make_engine
from app.migrate import run
from app.services.authorization import Authorizer
from app.services.ports import Identity

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    run("upgrade", database_url)
    yield eng
    eng.dispose()


def test_configured_admin_is_allowed_and_others_are_not(engine) -> None:  # type: ignore[no-untyped-def]
    seed_initial_admin(engine, "configured-admin@example.test", "configured-admin@example.test")
    auth = Authorizer(SqlAllowlistRepository(engine), "email")

    user = auth.authorize(Identity(email="configured-admin@example.test"))
    assert user is not None and user.role == "administrator"
    assert auth.authorize(Identity(email="someone-else@example.test")) is None


def test_seeding_is_idempotent_and_reactivates(engine) -> None:  # type: ignore[no-untyped-def]
    seed_initial_admin(engine, "a@example.test")
    with engine.begin() as conn:
        conn.execute(text("UPDATE allowlist_entry SET active = false, role = 'global_manager'"))
    assert SqlAllowlistRepository(engine).find_active("a@example.test") is None

    seed_initial_admin(engine, "a@example.test")
    seed_initial_admin(engine, "a@example.test")
    record = SqlAllowlistRepository(engine).find_active("a@example.test")
    assert record is not None and record.role == "administrator"
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM allowlist_entry")).scalar_one() == 1


def test_removed_identity_loses_access_even_with_a_google_session(engine) -> None:  # type: ignore[no-untyped-def]
    seed_initial_admin(engine, "gone@example.test")
    auth = Authorizer(SqlAllowlistRepository(engine), "email")
    assert auth.authorize(Identity(email="gone@example.test")) is not None
    with engine.begin() as conn:
        conn.execute(text("UPDATE allowlist_entry SET active = false"))
    assert auth.authorize(Identity(email="gone@example.test")) is None


def test_no_admin_identity_is_hardcoded_in_source() -> None:
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[2] / "app"
    hits = [
        str(p)
        for p in root.rglob("*.py")
        if re.search(r"[\w.+-]+@(?!example\.test)[\w-]+\.\w+", p.read_text())
    ]
    assert hits == []
