"""The dashboard from recorded data (RF-15, P-04), checked against figures worked out by hand."""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import text

from app.adapters.db.metrics import SqlMetricsRepository
from app.services.metrics import MetricsService
from tests.integration.batch_helpers import ADMIN
from tests.integration.test_api import principal_headers

pytestmark = pytest.mark.integration

MANAGER = "manager@example.test"
TODAY = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def incident(api: Any, provider: str, order: str, **cols: Any) -> None:
    base = {
        "provider": provider,
        "order_id": order,
        "incident_date": "2026-11-01",
        "state": "claimed",
        **cols,
    }
    names = ", ".join(base)
    marks = ", ".join(f":{k}" for k in base)
    with api.engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO incident ({names}, source, created_by) VALUES ({marks}, 'import', 'seed')"
            ),
            base,
        )


@pytest.fixture
def dash(client):  # type: ignore[no-untyped-def]
    """Seven claims, an incident not claimed yet, and a clock fixed on 2026-11-23."""
    client.app.state.metrics_service = MetricsService(
        SqlMetricsRepository(client.engine), clock=lambda: TODAY
    )
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) "
                "VALUES (gen_random_uuid(), :m, :m, 'global_manager')"
            ),
            {"m": MANAGER},
        )
    # Uber Eats / Just Eat: the email channel
    incident(
        client,
        "uber eats",
        "U1",
        branch="centro",
        state="resolved",
        claim_date="2026-11-10",
        claim_amount="10.00",
        recovered_amount="4.00",
        recovery_date="2026-11-15",
    )
    incident(
        client, "uber eats", "U2", branch="centro", claim_date="2026-11-11", claim_amount="5.50"
    )
    incident(client, "uber eats", "U3", state="rejected", claim_date="2026-11-12")  # no amount
    incident(
        client,
        "uber eats",
        "U4",
        branch="centro",
        state="resolved",
        claim_date="2026-11-13",
        claim_amount="20.00",
    )  # resolved, recovered amount unknown
    incident(
        client,
        "just eat",
        "J1",
        state="resolved",
        claim_date="2026-11-14",
        claim_amount="7.25",
        recovered_amount="7.25",
        recovery_date="2026-11-16",
    )
    incident(client, "uber eats", "U5", state="pending_send")  # imported, never claimed
    # Glovo: claimed by hand
    incident(client, "glovo", "G1", branch="norte", claim_date="2026-11-09", claim_amount="30.00")
    incident(
        client,
        "glovo",
        "G2",
        branch="norte",
        state="resolved",
        claim_date="2026-10-01",
        claim_amount="10.00",
        recovered_amount="8.00",
        recovery_date="2026-11-05",
    )
    return client


def metrics(api: Any, who: str = ADMIN, **params: Any) -> Any:
    return api.get("/api/metrics", params=params, headers=principal_headers(who))


def channel(body: dict[str, Any], name: str) -> dict[str, Any]:
    return next(c for c in body["channels"] if c["channel"] == name)


# --- the figures, by hand ------------------------------------------------------------------------------------


def test_the_default_date_is_the_claim_date_and_the_response_says_so(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash).json()
    assert body["dateKind"] == "claim"
    assert body["criteria"] == {"status": "approved", "pendingDecision": None}


def test_the_email_channel_counts_claims_recoveries_and_known_amounts(dash) -> None:  # type: ignore[no-untyped-def]
    email = channel(metrics(dash).json(), "email")
    # claims U1..U4 and J1; amounts 10.00 + 5.50 + 20.00 + 7.25 (U3 has none)
    assert (email["claimedCount"], email["claimedAmount"], email["incompleteCount"]) == (
        5,
        "42.75",
        1,
    )
    # recoveries are the Resuelta ones: U1, U4 and J1; U4 has no recorded amount
    assert (email["recoveredCount"], email["recoveredAmount"]) == (3, "11.25")
    assert email["recoveryRate"] == "0.6000"  # 3 of 5 claims, pending and rejected included


def test_glovo_is_kept_apart_from_email(dash) -> None:  # type: ignore[no-untyped-def]
    glovo = channel(metrics(dash).json(), "glovo")
    assert (glovo["claimedCount"], glovo["claimedAmount"]) == (2, "40.00")
    assert (glovo["recoveredCount"], glovo["recoveredAmount"], glovo["recoveryRate"]) == (
        1,
        "8.00",
        "0.5000",
    )
    assert glovo["incompleteCount"] == 0


def test_an_incident_that_was_never_claimed_is_not_counted(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash).json()
    assert sum(c["claimedCount"] for c in body["channels"]) == 7
    assert all(b["provider"] != "uber eats" or b["claimedCount"] > 0 for b in body["breakdown"])


def test_the_warning_counts_incidents_with_a_missing_amount(dash) -> None:  # type: ignore[no-untyped-def]
    warnings = metrics(dash).json()["warnings"]
    # U3 has no claim amount and U4 is resolved without a recovered amount
    assert warnings == [
        {
            "code": "incomplete_amounts",
            "message": "Hay 2 incidencias sin importe: los totales están incompletos.",
            "count": 2,
        }
    ]


def test_the_breakdown_is_by_provider_and_branch_with_sin_sucursal_apart(dash) -> None:  # type: ignore[no-untyped-def]
    rows = {(b["provider"], b["branch"]): b for b in metrics(dash).json()["breakdown"]}
    assert rows[("uber eats", "centro")]["claimedCount"] == 3
    assert rows[("uber eats", "centro")]["claimedAmount"] == "35.50"
    assert rows[("uber eats", None)]["claimedAmount"] is None  # absent, never zero
    assert rows[("uber eats", None)]["incompleteCount"] == 1
    assert (
        rows[("just eat", None)]["claimedAmount"],
        rows[("just eat", None)]["recoveredAmount"],
    ) == ("7.25", "7.25")


# --- pending claims and their age ----------------------------------------------------------------------------------------


def test_pending_claims_are_listed_oldest_first_with_calendar_days(dash) -> None:  # type: ignore[no-untyped-def]
    pending = metrics(dash).json()["pendingClaims"]
    assert [(p["claimDate"], p["ageDays"]) for p in pending] == [
        ("2026-11-09", 14),
        ("2026-11-11", 12),
    ]
    assert [p["provider"] for p in pending] == ["glovo", "uber eats"]


# --- filters and the other dates -------------------------------------------------------------------------------------------------


def test_a_claim_date_range_counts_only_the_claims_of_that_period(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash, **{"from": "2026-11-10", "to": "2026-11-12"}).json()
    email = channel(body, "email")
    assert (email["claimedCount"], email["recoveredCount"], email["recoveryRate"]) == (
        3,
        1,
        "0.3333",
    )
    glovo = channel(body, "glovo")
    assert (glovo["claimedCount"], glovo["claimedAmount"], glovo["recoveryRate"]) == (0, None, None)
    assert [p["claimDate"] for p in body["pendingClaims"]] == ["2026-11-11"]


def test_provider_and_branch_filters_narrow_the_figures(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash, provider="uber eats", branch="centro").json()
    assert channel(body, "email")["claimedCount"] == 3
    assert channel(body, "glovo")["claimedCount"] == 0
    none = metrics(dash, branch="none").json()
    assert channel(none, "email")["claimedCount"] == 2  # U3 and J1 have no branch


def test_with_the_recovery_date_the_rate_is_not_calculable(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash, dateKind="recovery", **{"from": "2026-11-01"}).json()
    assert body["dateKind"] == "recovery"
    assert [c["recoveryRate"] for c in body["channels"]] == [None, None]
    assert channel(body, "email")["recoveredCount"] == 2  # U1 and J1 (U4 has no recovery date)
    assert channel(body, "glovo")["recoveredCount"] == 1  # G2 on 2026-11-05


def test_by_incident_date_the_claims_of_those_incidents_are_counted(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash, dateKind="incident", **{"from": "2026-11-01", "to": "2026-11-30"}).json()
    assert body["dateKind"] == "incident"
    assert (
        channel(body, "email")["claimedCount"] == 5
        and channel(body, "email")["recoveryRate"] == "0.6000"
    )


def test_nothing_in_the_period_is_empty_with_a_no_data_warning(dash) -> None:  # type: ignore[no-untyped-def]
    body = metrics(dash, **{"from": "2030-01-01", "to": "2030-01-31"}).json()
    assert body["channels"] == [] and body["breakdown"] == [] and body["pendingClaims"] == []
    assert body["warnings"] == [
        {"code": "no_data", "message": "No hay datos para el periodo seleccionado.", "count": 0}
    ]


def test_a_period_without_claims_has_no_rate_and_no_amounts_not_zero(dash) -> None:  # type: ignore[no-untyped-def]
    with dash.engine.begin() as conn:
        conn.execute(text("UPDATE incident SET claim_date = NULL, state = 'pending_send'"))
    body = metrics(dash, dateKind="incident").json()
    for c in body["channels"]:
        assert (c["claimedCount"], c["claimedAmount"], c["recoveredAmount"], c["recoveryRate"]) == (
            0,
            None,
            None,
            None,
        )


def test_the_amounts_keep_their_digits(dash) -> None:  # type: ignore[no-untyped-def]
    incident(dash, "glovo", "G3", claim_date="2026-11-20", claim_amount="0.1234")
    glovo = channel(metrics(dash, **{"from": "2026-11-20", "to": "2026-11-20"}).json(), "glovo")
    assert glovo["claimedAmount"] == "0.1234"


# --- access, environment and isolation (6.3) ------------------------------------------------------------------------------------------


def test_a_read_only_role_can_read_the_dashboard_and_no_session_cannot(dash) -> None:  # type: ignore[no-untyped-def]
    assert metrics(dash, who=MANAGER).status_code == 200
    assert dash.get("/api/metrics").status_code == 401


def test_the_figures_name_their_environment_and_only_use_its_own_data(dash) -> None:  # type: ignore[no-untyped-def]
    assert metrics(dash).json()["environment"] == "test"
    dash.app.state.settings.app_env = "production"
    assert metrics(dash).json()["environment"] == "production"
    # Each environment has its own database: this request reads only the rows of this one.
    with dash.engine.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM incident")).scalar()
    assert total == 8


def test_invalid_filters_are_refused(dash) -> None:  # type: ignore[no-untyped-def]
    for params in ({"dateKind": "weird"}, {"from": "2026-02-30"}, {"provider": "rappi"}):
        assert metrics(dash, **params).status_code == 422
