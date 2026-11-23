"""Business schema (change 2, phase 1): reversible migrations and the rules the database holds."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.adapters.db.engine import make_engine
from app.migrate import run

pytestmark = pytest.mark.integration

PLATFORM = {"allowlist_entry", "technical_check"}
BUSINESS = {
    "provider",
    "branch",
    "batch",
    "batch_row",
    "incident",
    "incident_history",
    "outbox",
    "audit_log",
    "setting",
}


@pytest.fixture
def engine(database_url: str):  # type: ignore[no-untyped-def]
    eng = make_engine(database_url)
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    yield eng
    eng.dispose()


def tables(engine) -> set[str]:  # type: ignore[no-untyped-def]
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_business_migration_goes_up_and_down(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    assert tables(engine) == PLATFORM | BUSINESS

    run("downgrade", database_url, "0001")
    assert tables(engine) == PLATFORM

    run("upgrade", database_url)
    assert tables(engine) == PLATFORM | BUSINESS

    run("downgrade", database_url, "base")
    assert tables(engine) == set()


def test_the_three_providers_exist_and_only_two_send_email(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT code, sends_email FROM provider ORDER BY code")).all()
    assert rows == [("glovo", False), ("just eat", True), ("uber eats", True)]


def _incident(
    order_id: str, provider: str = "uber eats", branch: str | None = None
) -> tuple[str, dict]:  # type: ignore[type-arg]
    return (
        "INSERT INTO incident (id, provider, order_id, incident_date, branch, state, "
        "source, created_by) VALUES (gen_random_uuid(), :provider, :order_id, "
        "'2026-11-02', :branch, 'imported_no_email', 'import', 'test')",
        {"provider": provider, "order_id": order_id, "branch": branch},
    )


def test_one_incident_per_provider_and_order_id(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    sql, params = _incident("A-1")
    with engine.begin() as conn:
        conn.execute(text(sql), params)
    # The branch is not part of the key (RN-01): another branch does not make a new incident.
    with pytest.raises(IntegrityError, match="uq_incident_key"), engine.begin() as conn:
        conn.execute(text(sql), params)
    # The same Order ID of another provider is another incident.
    other_sql, other_params = _incident("A-1", provider="just eat")
    with engine.begin() as conn:
        conn.execute(text(other_sql), other_params)


def test_order_id_is_kept_exactly_with_case_and_spaces(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    with engine.begin() as conn:
        for order_id in ("ab-1", "AB-1", " AB-1"):
            sql, params = _incident(order_id)
            conn.execute(text(sql), params)
        count = conn.execute(text("SELECT count(*) FROM incident")).scalar()
    assert count == 3


def _batch(owner: str, state: str) -> str:
    return (
        "INSERT INTO batch (id, owner, state, file_name, size_bytes, blob_name) "
        f"VALUES (gen_random_uuid(), '{owner}', '{state}', 'f.xlsx', 1, 'b/' || gen_random_uuid())"
    )


@pytest.mark.parametrize("state", ["uploaded", "processing", "in_review"])
def test_a_user_has_one_unconfirmed_batch(engine, database_url: str, state: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    with engine.begin() as conn:
        conn.execute(text(_batch("ana", state)))
    with pytest.raises(IntegrityError, match="uq_batch_one_unconfirmed"), engine.begin() as conn:
        conn.execute(text(_batch("ana", "uploaded")))
    # Another user is not affected.
    with engine.begin() as conn:
        conn.execute(text(_batch("luis", "uploaded")))


@pytest.mark.parametrize("state", ["rejected", "discarded", "confirmed", "completed"])
def test_finished_batches_do_not_count_as_unconfirmed(  # type: ignore[no-untyped-def]
    engine, database_url: str, state: str
) -> None:
    run("upgrade", database_url)
    with engine.begin() as conn:
        conn.execute(text(_batch("ana", state)))
        conn.execute(text(_batch("ana", state)))
        conn.execute(text(_batch("ana", "uploaded")))


def test_unknown_values_are_refused(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    with pytest.raises(IntegrityError, match="ck_batch_state"), engine.begin() as conn:
        conn.execute(text(_batch("ana", "weird")))
    with pytest.raises(IntegrityError), engine.begin() as conn:
        sql, params = _incident("Z-1", provider="rappi")
        conn.execute(text(sql), params)


def test_amounts_keep_their_digits(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    sql, params = _incident("D-1")
    with engine.begin() as conn:
        conn.execute(text(sql), params)
        conn.execute(
            text(
                "UPDATE incident SET claim_amount = '12.345', provider_costs = '-0.10', total = '0'"
            )
        )
        got = conn.execute(
            text("SELECT claim_amount::text, provider_costs::text, total::text FROM incident")
        ).one()
    assert got == ("12.345", "-0.10", "0")


def test_an_absent_amount_is_null_not_zero(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    sql, params = _incident("N-1")
    with engine.begin() as conn:
        conn.execute(text(sql), params)
        got = conn.execute(text("SELECT claim_amount, incident_time FROM incident")).one()
    assert got == (None, None)


def test_one_outbox_record_per_incident(engine, database_url: str) -> None:  # type: ignore[no-untyped-def]
    run("upgrade", database_url)
    sql, params = _incident("O-1")
    with engine.begin() as conn:
        conn.execute(text(sql), params)
        incident = conn.execute(text("SELECT id FROM incident")).scalar()
        conn.execute(text(_batch("ana", "confirmed")))
        batch = conn.execute(text("SELECT id FROM batch")).scalar()
    insert = text(
        "INSERT INTO outbox (id, incident_id, batch_id, state, recipient, template_version) "
        "VALUES (gen_random_uuid(), :i, :b, 'pending', 'test@example.test', 'v0')"
    )
    with engine.begin() as conn:
        conn.execute(insert, {"i": incident, "b": batch})
    with pytest.raises(IntegrityError, match="uq_outbox_incident"), engine.begin() as conn:
        conn.execute(insert, {"i": incident, "b": batch})
