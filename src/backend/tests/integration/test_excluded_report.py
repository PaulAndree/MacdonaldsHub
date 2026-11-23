"""The excluded-rows report (RF-20): rows and reasons in a file that can be corrected and re-uploaded."""

import io
import zipfile
from typing import Any

import pytest
from sqlalchemy import text

from app.adapters.xlsx.reader import read_xlsx
from tests.integration.batch_helpers import (
    ADMIN,
    ROW,
    SAMPLES,
    seed_incident,
    service,
    staged,
    upload,
)
from tests.integration.test_api import principal_headers
from tests.xlsx_builder import simple

pytestmark = pytest.mark.integration

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def prepared(client: Any, content: bytes, who: str = ADMIN) -> str:
    batch_id = upload(client, content, who)
    service(client).process_pending()
    return batch_id


def report(client: Any, batch_id: str, who: str = ADMIN) -> Any:
    return client.get(f"/api/batches/{batch_id}/excluded-report", headers=principal_headers(who))


def sheet_text(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return z.read("xl/worksheets/sheet1.xml").decode("utf-8")


def sample(client: Any) -> str:
    return prepared(client, (SAMPLES / "incidencias.xlsx").read_bytes())


def test_the_report_is_an_xlsx_download(client) -> None:  # type: ignore[no-untyped-def]
    response = report(client, sample(client))
    assert response.status_code == 200
    assert response.headers["content-type"] == XLSX
    assert "attachment" in response.headers["content-disposition"]
    assert zipfile.is_zipfile(io.BytesIO(response.content))


def test_it_holds_every_excluded_row_with_its_class_and_reason_and_no_new_row(client) -> None:  # type: ignore[no-untyped-def]
    content = report(client, sample(client)).content
    sheet = read_xlsx(content)
    assert len(sheet.rows) == 10  # 2 duplicate + 2 conflict + 6 error, none of the 8 new
    body = sheet_text(content)
    for label in ("Motivo", "Clase", "Duplicada", "En conflicto", "Con error"):
        assert label in body
    assert "El proveedor «rappi» no es uno de los conocidos." in body
    assert "UE-100001" not in body  # a new row is not excluded


def test_error_rows_keep_what_the_file_said_so_the_user_can_correct_it(client) -> None:  # type: ignore[no-untyped-def]
    body = sheet_text(report(client, sample(client)).content)
    assert "12,50 €" in body
    assert "06/11/2026" in body
    assert "playa" in body


def test_amounts_go_back_as_numeric_cells_and_ids_as_text(client) -> None:  # type: ignore[no-untyped-def]
    sheet = read_xlsx(report(client, sample(client)).content)
    duplicates = [
        r for r in sheet.rows if "order_id" in r.cells and r.cells["order_id"].text == "UE-100010"
    ]
    assert duplicates and all(r.cells["claim_amount"].kind == "number" for r in duplicates)
    with_id = [r for r in sheet.rows if "order_id" in r.cells]  # one row has no Order ID at all
    assert len(with_id) == 9 and all(r.cells["order_id"].kind == "text" for r in with_id)


def test_the_report_can_be_corrected_and_uploaded_again_without_a_second_email(client) -> None:  # type: ignore[no-untyped-def]
    # Rows of the file that are already confirmed come back as duplicates, never as new.
    seed_incident(client)
    first = prepared(client, simple([ROW]))
    content = report(client, first).content
    with client.engine.begin() as conn:
        conn.execute(text("UPDATE batch SET state = 'discarded'"))
    again = prepared(client, content)
    assert [(n, c) for n, c, _ in staged(client, again)] == [(2, "duplicate")]
    with client.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM outbox")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM incident")).scalar() == 1


def test_a_batch_with_nothing_excluded_gives_an_empty_report(client) -> None:  # type: ignore[no-untyped-def]
    response = report(client, prepared(client, simple([ROW])))
    assert response.status_code == 200
    assert read_xlsx(response.content).rows == []


def test_there_is_no_report_before_the_batch_is_prepared_or_for_another_user(client) -> None:  # type: ignore[no-untyped-def]
    waiting = upload(client, simple([ROW]))
    assert report(client, waiting).status_code == 404
    assert report(client, "00000000-0000-0000-0000-000000000000").status_code == 404
    with client.engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) VALUES "
                "(gen_random_uuid(), 'o@example.test', 'o@example.test', 'administrator')"
            )
        )
    service(client).process_pending()
    assert report(client, waiting, who="o@example.test").status_code == 404
