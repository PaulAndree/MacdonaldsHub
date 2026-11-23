"""The preview served from staging (RF-03, RF-04, RF-05, RNF-01): classes, reasons, versions."""

from typing import Any

import pytest
from sqlalchemy import text

from tests.integration.batch_helpers import (
    ADMIN,
    ROW,
    SAMPLES,
    no_definitive_records,
    seed_incident,
    service,
    upload,
)
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import HEADERS, simple

pytestmark = pytest.mark.integration


def prepared(client: Any, content: bytes) -> str:
    batch_id = upload(client, content)
    service(client).process_pending()
    return batch_id


def rows(client: Any, batch_id: str, who: str = ADMIN, **params: Any) -> Any:
    return client.get(
        f"/api/batches/{batch_id}/rows", params=params, headers=principal_headers(who)
    )


def sample(client: Any) -> str:
    return prepared(client, (SAMPLES / "incidencias.xlsx").read_bytes())


# --- counts per class and the summary ----------------------------------------------------------------------


def test_the_batch_summary_counts_each_class_and_what_confirming_would_create(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = sample(client)
    batch = client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()
    assert batch["state"] == "in_review"
    assert batch["summary"] == {
        "totals": {"new": 8, "duplicate": 2, "conflict": 2, "error": 6},
        "incidentsToCreate": 8,
        "emailsToGenerate": 7,  # the Uber Eats and Just Eat ones
        "withoutEmail": 1,  # Glovo: GL-9001
    }


def test_there_is_no_summary_before_the_batch_is_prepared(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = upload(client, simple([ROW]))
    batch = client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()
    assert batch["summary"] is None


# --- rows -------------------------------------------------------------------------------------------------------


def test_every_row_has_one_class_and_the_totals_cover_the_whole_batch(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = sample(client)
    body = rows(client, batch_id).json()
    assert body["total"] == 18
    assert body["totalsByClass"] == {"new": 8, "duplicate": 2, "conflict": 2, "error": 6}
    assert [r["rowNumber"] for r in body["items"]] == list(range(2, 20))
    assert {r["class"] for r in body["items"]} == {"new", "duplicate", "conflict", "error"}


def test_filtering_by_class_keeps_the_totals_of_the_whole_batch(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = sample(client)
    body = rows(client, batch_id, **{"class": "error"}).json()
    assert body["total"] == 6
    assert all(r["class"] == "error" for r in body["items"])
    assert body["totalsByClass"]["new"] == 8


def test_every_excluded_row_has_a_reason_and_a_new_row_has_none(client) -> None:  # type: ignore[no-untyped-def]
    items = rows(client, sample(client)).json()["items"]
    for item in items:
        assert (item["reason"] is None) == (item["class"] == "new")
    reasons = {i["reason"] for i in items if i["class"] == "error"}
    assert "El proveedor «rappi» no es uno de los conocidos." in reasons
    assert "La sucursal «playa» no es una sucursal conocida." in reasons


def test_error_rows_show_what_the_file_said_not_a_repaired_value(client) -> None:  # type: ignore[no-untyped-def]
    items = rows(client, sample(client), **{"class": "error"}).json()["items"]
    by_order = {i["fields"]["orderId"]: i["fields"] for i in items}
    assert by_order["JE-55004"]["incidentDate"] == "06/11/2026"
    assert by_order["JE-55005"]["claimAmount"] == "12,50 €"
    assert by_order["UE-100005"]["branch"] == "playa"
    assert by_order["100004"]["orderId"] == "100004"  # the numeric Order ID, as typed
    assert by_order["JE-55004"]["incidentTime"] is None


def test_valid_rows_show_normalized_text_with_precision_and_absence(client) -> None:  # type: ignore[no-untyped-def]
    items = rows(client, sample(client), **{"class": "new"}).json()["items"]
    by_order = {i["fields"]["orderId"]: i["fields"] for i in items}
    first = by_order["UE-100001"]
    assert (first["provider"], first["incidentDate"], first["incidentTime"]) == (
        "uber eats",
        "2026-11-02",
        "12:15",
    )
    assert first["claimAmount"] == "12.5" and first["providerCosts"] == "3.1"
    assert by_order["UE-100002"]["incidentTime"] is None  # no time in the source: none invented
    assert by_order["UE-100002"]["claimAmount"] == "0.1234"
    assert by_order["JE-55002"]["branch"] is None and by_order["JE-55002"]["claimAmount"] is None
    assert by_order["UE-100003"]["provider"] == "uber eats"  # lowercased
    assert by_order["UE-100003"]["branch"] == "norte"
    assert by_order["UE-100003"]["claimAmount"] == "-4.2"  # the sign of the source


def test_repeated_keys_in_the_file_name_the_other_rows(client) -> None:  # type: ignore[no-untyped-def]
    items = rows(client, sample(client)).json()["items"]
    repeated = {
        i["fields"]["orderId"]: i
        for i in items
        if i["fields"]["orderId"] in ("UE-100010", "JE-55010")
    }
    ue = [i for i in items if i["fields"]["orderId"] == "UE-100010"]
    assert [i["class"] for i in ue] == ["duplicate", "duplicate"]
    assert ue[0]["repeatedInFile"] == [ue[1]["rowNumber"]]
    assert ue[1]["repeatedInFile"] == [ue[0]["rowNumber"]]
    je = [i for i in items if i["fields"]["orderId"] == "JE-55010"]
    assert [i["class"] for i in je] == ["conflict", "conflict"]
    assert je[0]["comparison"] is None  # a conflict inside the file has no stored version
    assert repeated


def test_a_conflict_with_an_existing_incident_shows_both_versions_and_the_differing_fields(
    client,
) -> None:  # type: ignore[no-untyped-def]
    seed_incident(client, claim="99")
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    batch_id = prepared(client, simple([[*ROW, ("n", "12.50")]], headers))
    (row,) = rows(client, batch_id).json()["items"]
    assert row["class"] == "conflict"
    assert row["fields"]["claimAmount"] == "12.50"
    comparison = row["comparison"]
    assert comparison["existing"]["claimAmount"] == "99"
    assert comparison["existing"]["orderId"] == "UE-1"
    assert comparison["differingFields"] == ["claimAmount"]


def test_a_duplicate_has_no_differences_to_show(client) -> None:  # type: ignore[no-untyped-def]
    seed_incident(client)
    (row,) = rows(client, prepared(client, simple([ROW]))).json()["items"]
    assert row["class"] == "duplicate" and row["comparison"] is None


# --- RNF-01: 600 rows and paging ----------------------------------------------------------------------------------


def test_a_large_batch_is_paged_without_losing_a_row(client) -> None:  # type: ignore[no-untyped-def]
    many = [[("s", "uber eats"), ("s", f"UE-{i:04d}"), ("s", "2026-11-02")] for i in range(600)]
    batch_id = prepared(client, simple(many))
    first = rows(client, batch_id, pageSize=200).json()
    assert (first["total"], first["pageSize"], first["page"]) == (600, 200, 1)
    seen = [r["rowNumber"] for r in first["items"]]
    for page in (2, 3):
        seen += [
            r["rowNumber"] for r in rows(client, batch_id, page=page, pageSize=200).json()["items"]
        ]
    assert seen == list(range(2, 602))
    assert rows(client, batch_id, page=4, pageSize=200).json()["items"] == []
    batch = client.get(f"/api/batches/{batch_id}", headers=principal_headers(ADMIN)).json()
    assert batch["summary"]["incidentsToCreate"] == 600


def test_the_page_size_has_the_limits_of_the_contract(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = sample(client)
    assert rows(client, batch_id, pageSize=201).status_code == 422
    assert rows(client, batch_id, pageSize=0).status_code == 422
    assert rows(client, batch_id, page=0).status_code == 422
    assert rows(client, batch_id, **{"class": "weird"}).status_code == 422


# --- access ------------------------------------------------------------------------------------------------------------


def test_rows_of_a_batch_that_is_not_prepared_or_not_yours_are_not_found(client) -> None:  # type: ignore[no-untyped-def]
    waiting = upload(client, simple([ROW]))
    assert rows(client, waiting).status_code == 404  # still being processed
    assert rows(client, "00000000-0000-0000-0000-000000000000").status_code == 404


def test_another_user_cannot_read_the_preview(client) -> None:  # type: ignore[no-untyped-def]
    batch_id = sample(client)
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), 'o@example.test', 'o@example.test', 'administrator')"
            )
        )
    assert rows(client, batch_id, who="o@example.test").status_code == 404


def test_the_preview_creates_nothing_definitive(client) -> None:  # type: ignore[no-untyped-def]
    rows(client, sample(client))
    no_definitive_records(client)
