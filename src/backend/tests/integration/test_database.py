import pytest
from sqlalchemy import inspect, text

from app.adapters.db.engine import make_engine, ping
from app.migrate import run

pytestmark = pytest.mark.integration


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    yield eng
    eng.dispose()


def tables(engine) -> set[str]:  # type: ignore[no-untyped-def]
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_connects_to_real_postgres(engine) -> None:  # type: ignore[no-untyped-def]
    assert ping(engine) is True


def test_upgrade_downgrade_reupgrade(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    # The platform tables come from revision 0001; later revisions add the business schema.
    platform = {"allowlist_entry", "technical_check"}
    run("upgrade", database_url, "0001")
    assert tables(engine) == platform

    run("downgrade", database_url, "base")
    assert tables(engine) == set()

    run("upgrade", database_url, "0001")
    assert tables(engine) == platform


def test_role_check_constraint(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    with pytest.raises(Exception, match="ck_allowlist_role"), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, role) "
                "VALUES (gen_random_uuid(), 'x', 'root')"
            )
        )


def test_identifier_is_unique(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    ins = text(
        "INSERT INTO allowlist_entry (id, identifier, role) "
        "VALUES (gen_random_uuid(), 'same', 'administrator')"
    )
    with engine.begin() as conn:
        conn.execute(ins)
    with pytest.raises(Exception, match="allowlist_entry_identifier_key"), engine.begin() as conn:
        conn.execute(ins)
