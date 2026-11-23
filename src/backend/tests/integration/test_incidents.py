"""Incident queries, export, results, corrections and manual entry (RF-16, RF-21, RF-22): E-12, E-13."""

import io
import zipfile
from typing import Any

import pytest
from sqlalchemy import text

from app.adapters.xlsx.reader import read_xlsx
from tests.integration.batch_helpers import ADMIN
from tests.integration.test_api import principal_headers

pytestmark = pytest.mark.integration

MANAGER = "manager@example.test"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture
def api(client):  # type: ignore[no-untyped-def]
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), :m, :m, 'global_manager')"
            ),
            {"m": MANAGER},
        )
    return client


def seed(client: Any, provider: str, order: str, **cols: Any) -> str:
    base = {
        "provider": provider,
        "order_id": order,
        "incident_date": "2026-11-10",
        "state": "imported_no_email" if provider == "glovo" else "pending_send",
        **cols,
    }
    names = ", ".join(base)
    marks = ", ".join(f":{k}" for k in base)
    with client.engine.begin() as conn:
        new = conn.execute(
            text(
                f"INSERT INTO incident ({names}, source, created_by) VALUES ({marks}, 'import', 'seed') "
                "RETURNING id::text"
            ),
            base,
        ).scalar()
        conn.execute(
            text(
                "INSERT INTO incident_history (incident_id, actor, kind, new) "
                "VALUES (:i, 'seed', 'imported', :s)"
            ),
            {"i": new, "s": base["state"]},
        )
    return new  # type: ignore[no-any-return]


def get(client: Any, path: str, who: str = ADMIN, **params: Any) -> Any:
    return client.get(path, params=params, headers=principal_headers(who))


def post(client: Any, path: str, body: Any, who: str = ADMIN) -> Any:
    return client.post(path, json=body, headers=principal_headers(who))


CORE = {
    "provider": "uber eats",
    "orderId": "UE-900",
    "incidentDate": "2026-11-21",
    "incidentTime": None,
    "branch": "centro",
    "claimAmount": "18.75",
    "providerCosts": None,
    "total": None,
    "description": "nota",
}


@pytest.fixture
def seeded(api):  # type: ignore[no-untyped-def]
    from app.adapters.db.catalog import seed_branches

    seed_branches(api.engine, ("centro", "norte"))
    ids = {
        "ue": seed(
            api,
            "uber eats",
            "UE-1",
            branch="centro",
            claim_amount="12.345",
            incident_time="19:40",
            incident_date="2026-11-10",
        ),
        "je": seed(api, "just eat", "JE-1", incident_date="2026-11-11"),
        "gl": seed(
            api, "glovo", "GL-1", branch="norte", claim_amount="30.00", incident_date="2026-11-12"
        ),
        "old": seed(
            api,
            "uber eats",
            "UE-0",
            branch="centro",
            state="claimed",
            claim_date="2026-10-30",
            incident_date="2026-10-28",
        ),
    }
    return api, ids


# --- 5.1: listing and detail ------------------------------------------------------------------------------------


def test_every_incident_is_listed_with_absent_values_kept(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    body = get(api, "/api/incidents").json()
    assert body["total"] == 4 and body["page"] == 1 and body["pageSize"] == 50
    by_order = {i["orderId"]: i for i in body["items"]}
    assert by_order["UE-1"]["claimAmount"] == "12.345"  # the digits of the source
    assert by_order["UE-1"]["incidentTime"] == "19:40"
    assert by_order["JE-1"]["branch"] is None and by_order["JE-1"]["claimAmount"] is None
    assert by_order["JE-1"]["incidentTime"] is None  # no time invented
    assert by_order["GL-1"]["channel"] == "glovo" and by_order["UE-1"]["channel"] == "email"
    assert by_order["JE-1"]["result"] is None and by_order["JE-1"]["recoveredAmount"] is None


def test_the_most_recent_incidents_come_first(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    dates = [i["incidentDate"] for i in get(api, "/api/incidents").json()["items"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.parametrize(
    ("params", "orders"),
    [
        ({"provider": "uber eats"}, {"UE-1", "UE-0"}),
        ({"branch": "centro"}, {"UE-1", "UE-0"}),
        ({"branch": "none"}, {"JE-1"}),
        ({"status": "claimed"}, {"UE-0"}),
        ({"from": "2026-11-11"}, {"JE-1", "GL-1"}),
        ({"to": "2026-11-10"}, {"UE-1", "UE-0"}),
        ({"from": "2026-11-11", "to": "2026-11-11"}, {"JE-1"}),
        ({"dateKind": "claim", "from": "2026-10-01"}, {"UE-0"}),
        ({"provider": "uber eats", "status": "pending_send"}, {"UE-1"}),
        ({"provider": "glovo", "branch": "centro"}, set()),
    ],
)
def test_filters_narrow_the_list(seeded, params: dict[str, str], orders: set[str]) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    body = get(api, "/api/incidents", **params).json()
    assert {i["orderId"] for i in body["items"]} == orders and body["total"] == len(orders)


def test_paging_reports_the_total_and_loses_nothing(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    first = get(api, "/api/incidents", pageSize=3).json()
    second = get(api, "/api/incidents", pageSize=3, page=2).json()
    assert (first["total"], len(first["items"]), len(second["items"])) == (4, 3, 1)
    assert len({i["id"] for i in first["items"] + second["items"]}) == 4


def test_a_filter_with_an_invalid_value_is_refused(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    for params in (
        {"provider": "rappi"},
        {"status": "x"},
        {"from": "2026-02-30"},
        {"pageSize": 500},
    ):
        assert get(api, "/api/incidents", **params).status_code == 422


def test_the_detail_has_the_incident_and_its_history(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    body = get(api, f"/api/incidents/{ids['ue']}").json()
    assert body["incident"]["orderId"] == "UE-1"
    assert [(h["kind"], h["field"], h["newValue"]) for h in body["history"]] == [
        ("imported", "status", "pending_send")
    ]
    assert get(api, "/api/incidents/00000000-0000-0000-0000-000000000000").status_code == 404
    assert get(api, "/api/incidents/not-an-id").status_code == 404


def test_the_branch_list_has_the_active_branches(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    assert [b["name"] for b in get(api, "/api/branches").json()["items"]] == [
        "centro",
        "norte",
        "sur",
    ]


def test_a_read_only_role_can_read_but_not_change(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    assert get(api, "/api/incidents", who=MANAGER).status_code == 200
    assert get(api, f"/api/incidents/{ids['ue']}", who=MANAGER).status_code == 200
    assert get(api, "/api/incidents/export", who=MANAGER).status_code == 200
    assert get(api, "/api/branches", who=MANAGER).status_code == 200
    for path, body in (
        (f"/api/incidents/{ids['gl']}/claim", {"claimDate": "2026-11-21"}),
        (
            f"/api/incidents/{ids['gl']}/result",
            {"result": "rejected", "recoveredAmount": None, "recoveryDate": None},
        ),
        ("/api/incidents/manual", CORE),
        ("/api/incidents/manual/check", CORE),
    ):
        assert post(api, path, body, who=MANAGER).status_code == 403


# --- 5.2: export -------------------------------------------------------------------------------------------------------


def test_the_export_holds_exactly_the_filtered_incidents_with_absent_values_explicit(
    seeded,
) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    response = get(api, "/api/incidents/export", provider="uber eats")
    assert response.status_code == 200 and response.headers["content-type"] == XLSX
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert "UE-1" in sheet and "UE-0" in sheet
    assert "JE-1" not in sheet and "GL-1" not in sheet
    assert "Sin hora" in sheet and "Importe desconocido" in sheet  # UE-0 has no time and no amount
    assert "<v>12.345</v>" in sheet  # the digits are kept, not rounded
    assert "<v>0</v>" not in sheet  # absent never becomes zero


def test_the_export_without_filters_has_every_incident_and_sin_sucursal(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    content = get(api, "/api/incidents/export").content
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
    assert all(o in sheet for o in ("UE-1", "UE-0", "JE-1", "GL-1")) and "Sin sucursal" in sheet
    assert read_xlsx is not None


# --- 5.3: manual claim, result and correction (E-12) ------------------------------------------------------------------------


def test_a_glovo_incident_can_be_claimed_by_hand(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    response = post(api, f"/api/incidents/{ids['gl']}/claim", {"claimDate": "2026-11-21"})
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["claimDate"]) == ("claimed", "2026-11-21")
    history = get(api, f"/api/incidents/{ids['gl']}").json()["history"]
    assert [(h["kind"], h["field"], h["newValue"]) for h in history[1:]] == [
        ("claim", "status", "claimed"),
        ("claim", "claimDate", "2026-11-21"),
    ]


def test_an_incident_with_an_email_or_already_claimed_cannot_be_claimed_by_hand(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    for key in ("ue", "old"):
        response = post(api, f"/api/incidents/{ids[key]}/claim", {"claimDate": "2026-11-21"})
        assert response.status_code == 409 and response.json()["code"] == "claim_not_available"


def test_a_partial_recovery_then_a_correction_keep_the_history_and_touch_nothing_else(
    seeded,
) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    incident = ids["old"]  # already claimed
    result = post(
        api,
        f"/api/incidents/{incident}/result",
        {"result": "resolved", "recoveredAmount": "12.00", "recoveryDate": "2026-11-15"},
    )
    assert result.status_code == 200
    body = result.json()
    assert (body["status"], body["result"], body["recoveredAmount"]) == (
        "resolved",
        "resolved",
        "12.00",
    )
    assert body["claimAmount"] is None  # the claimed amount is untouched and still absent

    corrected = post(
        api,
        f"/api/incidents/{incident}/corrections",
        {
            "result": "resolved",
            "recoveredAmount": "8.00",
            "recoveryDate": "2026-11-15",
            "reason": "El importe recuperado era 8,00.",
        },
    )
    assert corrected.status_code == 200
    detail = corrected.json()
    assert detail["incident"]["recoveredAmount"] == "8.00"
    last = detail["history"][-1]
    assert (last["kind"], last["field"], last["previousValue"], last["newValue"]) == (
        "correction",
        "recoveredAmount",
        "12.00",
        "8.00",
    )
    assert last["reason"] == "El importe recuperado era 8,00."
    # No batch, no outbox and no other incident moved.
    with api.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM outbox")).scalar() == 0
        assert (
            conn.execute(text("SELECT count(*) FROM incident WHERE state = 'resolved'")).scalar()
            == 1
        )


def test_the_history_is_append_only_and_in_order(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    post(api, f"/api/incidents/{ids['gl']}/claim", {"claimDate": "2026-11-21"})
    post(
        api,
        f"/api/incidents/{ids['gl']}/result",
        {"result": "resolved", "recoveredAmount": "10", "recoveryDate": "2026-11-22"},
    )
    post(
        api,
        f"/api/incidents/{ids['gl']}/corrections",
        {
            "result": "rejected",
            "recoveredAmount": None,
            "recoveryDate": None,
            "reason": "se rechazó",
        },
    )
    history = get(api, f"/api/incidents/{ids['gl']}").json()["history"]
    kinds = [h["kind"] for h in history]
    assert kinds == [
        "imported",
        "claim",
        "claim",
        "result",
        "result",
        "result",
        "correction",
        "correction",
        "correction",
    ]
    with api.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM incident_history")).scalar() == len(history) + 3
        )


def test_a_result_needs_a_claimed_incident_and_a_correction_needs_a_result(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    body = {"result": "resolved", "recoveredAmount": "1", "recoveryDate": "2026-11-15"}
    refused = post(api, f"/api/incidents/{ids['gl']}/result", body)
    assert refused.status_code == 409 and refused.json()["code"] == "incident_not_claimed"
    none = post(api, f"/api/incidents/{ids['gl']}/corrections", {**body, "reason": "x"})
    assert none.status_code == 409 and none.json()["code"] == "no_result_to_correct"


def test_the_recovered_amount_has_no_restriction_and_keeps_its_digits(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    response = post(
        api,
        f"/api/incidents/{ids['old']}/result",
        {"result": "resolved", "recoveredAmount": "1234.56789", "recoveryDate": None},
    )
    assert (
        response.json()["recoveredAmount"] == "1234.56789"
        and response.json()["recoveryDate"] is None
    )


@pytest.mark.parametrize(
    "body",
    [
        {"result": "maybe", "recoveredAmount": None, "recoveryDate": None},
        {"result": "resolved", "recoveredAmount": "12,50 €", "recoveryDate": None},
        {"result": "resolved", "recoveredAmount": None, "recoveryDate": "2026-02-30"},
        {"result": "resolved"},
    ],
)
def test_a_malformed_result_is_refused(seeded, body: dict[str, Any]) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    assert post(api, f"/api/incidents/{ids['old']}/result", body).status_code == 422


def test_a_correction_needs_a_reason(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    body = {"result": "resolved", "recoveredAmount": "1", "recoveryDate": None, "reason": ""}
    assert post(api, f"/api/incidents/{ids['old']}/corrections", body).status_code == 422


def test_changes_are_audited_with_the_actor(seeded) -> None:  # type: ignore[no-untyped-def]
    api, ids = seeded
    post(api, f"/api/incidents/{ids['gl']}/claim", {"claimDate": "2026-11-21"})
    with api.engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT actor, outcome, object_id FROM audit_log WHERE operation = 'incident.claim'"
            )
        ).one()
    assert row == (ADMIN, "success", ids["gl"])


# --- 5.4: manual entry (E-13, P-12) -------------------------------------------------------------------------------------------


def test_checking_a_new_key_creates_nothing(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    check = post(api, "/api/incidents/manual/check", CORE).json()
    assert check == {"outcome": "new", "existing": None, "differingFields": []}
    with api.engine.connect() as conn:
        assert (
            conn.execute(text("SELECT count(*) FROM incident WHERE order_id = 'UE-900'")).scalar()
            == 0
        )


def test_checking_an_existing_key_says_duplicate_or_conflict_with_the_stored_version(
    seeded,
) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    same = {
        **CORE,
        "orderId": "UE-1",
        "incidentDate": "2026-11-10",
        "incidentTime": "19:40",
        "claimAmount": "12.345",
        "description": None,
    }
    assert post(api, "/api/incidents/manual/check", same).json()["outcome"] == "duplicate"
    other = post(api, "/api/incidents/manual/check", {**same, "claimAmount": "99"}).json()
    assert other["outcome"] == "conflict" and other["differingFields"] == ["claimAmount"]
    assert other["existing"]["claimAmount"] == "12.345" and other["existing"]["orderId"] == "UE-1"


def test_an_existing_key_is_a_409_and_creates_nothing(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    response = post(api, "/api/incidents/manual", {**CORE, "orderId": "UE-1"})
    assert response.status_code == 409 and response.json()["code"] == "incident_exists"
    with api.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 4


def test_a_reviewed_new_entry_is_saved_once_without_email_and_with_audit(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    created = post(api, "/api/incidents/manual", CORE)
    assert created.status_code == 201
    body = created.json()
    assert body["batchId"] is None and body["status"] == "imported_no_email"
    assert (body["orderId"], body["claimAmount"], body["incidentTime"]) == ("UE-900", "18.75", None)
    assert post(api, "/api/incidents/manual", CORE).status_code == 409  # not twice
    with api.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM outbox")).scalar() == 0  # P-12: no email
        assert (
            conn.execute(text("SELECT source FROM incident WHERE order_id = 'UE-900'")).scalar()
            == "manual"
        )
        audit = conn.execute(
            text("SELECT actor, outcome FROM audit_log WHERE operation = 'incident.create_manual'")
        ).all()
    assert audit == [(ADMIN, "success")]
    detail = get(api, f"/api/incidents/{body['id']}").json()
    assert [(h["kind"], h["newValue"]) for h in detail["history"]] == [
        ("imported", "imported_no_email")
    ]


def test_a_manual_entry_can_then_be_claimed_by_hand(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    incident = post(api, "/api/incidents/manual", CORE).json()["id"]
    assert (
        post(api, f"/api/incidents/{incident}/claim", {"claimDate": "2026-11-21"}).status_code
        == 200
    )


@pytest.mark.parametrize(
    "change",
    [
        {"orderId": ""},
        {"provider": "rappi"},
        {"incidentDate": "21/11/2026"},
        {"incidentDate": "2026-02-30"},
        {"incidentTime": "25:00"},
        {"claimAmount": "12,50 €"},
        {"branch": "playa"},
    ],
)
def test_an_invalid_manual_entry_is_refused_and_creates_nothing(
    seeded, change: dict[str, Any]
) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    assert post(api, "/api/incidents/manual", {**CORE, **change}).status_code == 422
    assert post(api, "/api/incidents/manual/check", {**CORE, **change}).status_code == 422
    with api.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 4


def test_the_order_id_and_description_are_kept_exactly(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    body = {**CORE, "orderId": " Ab-1 ", "description": 'línea 1\nlínea 2 "x"'}
    created = post(api, "/api/incidents/manual", body).json()
    assert created["orderId"] == " Ab-1 " and created["description"] == 'línea 1\nlínea 2 "x"'


def test_the_branch_is_lowercased_as_in_the_file(seeded) -> None:  # type: ignore[no-untyped-def]
    api, _ = seeded
    assert (
        post(api, "/api/incidents/manual", {**CORE, "branch": "Centro"}).json()["branch"]
        == "centro"
    )
