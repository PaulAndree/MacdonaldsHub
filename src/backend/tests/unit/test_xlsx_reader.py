"""Reading the .xlsx package (RF-02, RN-06, RN-09, RN-10, BE-12, BE-17), with synthetic files."""

import io
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from app.adapters.xlsx.reader import MAX_FILE_BYTES, XlsxRejected, read_xlsx
from app.domain.rows import Cell, read_row
from tests.xlsx_builder import HEADERS, build, simple

BRANCHES = frozenset({"centro", "norte", "sur"})


def values(data: bytes):  # type: ignore[no-untyped-def]
    return read_xlsx(data).rows


def one(data: bytes) -> dict[str, Cell]:
    (row,) = values(data)
    return row.cells


# --- structure ------------------------------------------------------


def test_a_file_with_the_three_mandatory_headers_is_read() -> None:
    sheet = read_xlsx(simple([[("s", "uber eats"), ("s", "UE-1"), ("s", "2026-11-02")]]))
    assert [r.row_number for r in sheet.rows] == [2]
    assert set(sheet.rows[0].cells) == {"provider", "order_id", "when"}


def test_the_whole_file_is_rejected_when_a_mandatory_header_is_missing() -> None:
    data = simple([], headers=[("s", "Proveedor"), ("s", "Fecha y hora")])
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(data)
    assert caught.value.reason == "missing_required_header"
    assert caught.value.detail == "Order ID"


def test_several_worksheets_reject_the_file() -> None:
    data = build([[HEADERS], [HEADERS]])
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(data)
    assert caught.value.reason == "multiple_worksheets"


def test_a_file_that_is_not_a_zip_is_corrupt() -> None:
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(b"this is not a spreadsheet")
    assert caught.value.reason == "corrupt_or_protected_file"


def test_a_password_protected_file_is_rejected_as_protected() -> None:
    ole2 = bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 512
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(ole2)
    assert caught.value.reason == "corrupt_or_protected_file"
    assert "protegido" in (caught.value.detail or "")


def test_a_zip_without_a_workbook_is_corrupt() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("hello.txt", "x")
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(out.getvalue())
    assert caught.value.reason == "corrupt_or_protected_file"


def test_a_file_with_no_header_row_is_rejected() -> None:
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(build([[]]))
    assert caught.value.reason == "missing_required_header"


def test_the_file_size_limit_is_10_mb() -> None:
    assert MAX_FILE_BYTES == 10 * 1024 * 1024
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(b"x" * (MAX_FILE_BYTES + 1))
    assert caught.value.reason == "corrupt_or_protected_file"
    assert "10 MB" in (caught.value.detail or "")


def test_a_zip_bomb_is_rejected_before_it_is_expanded() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", b"0" * (300 * 1024 * 1024))
    assert len(out.getvalue()) < MAX_FILE_BYTES
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(out.getvalue())
    assert caught.value.reason == "corrupt_or_protected_file"
    assert "seguro" in (caught.value.detail or "")


def test_an_xml_with_a_doctype_is_rejected() -> None:
    bomb = '<!DOCTYPE x [<!ENTITY a "aaaa">]>'
    with pytest.raises(XlsxRejected):
        read_xlsx(simple([], doctype=bomb))


def test_the_sheet_is_found_through_the_relationships() -> None:
    data = simple([[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02")]], sheet_prefix="")
    assert len(values(data)) == 1


# --- a curated file (P-09) ------------------------------------------


def test_extra_columns_are_ignored() -> None:
    headers = [*HEADERS, ("s", "Notas internas")]
    data = simple(
        [[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02"), ("s", "ignore me")]], headers
    )
    assert set(one(data)) == {"provider", "order_id", "when"}


def test_completely_empty_rows_are_skipped_and_row_numbers_follow_the_file() -> None:
    data = simple(
        [
            [("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02")],
            [],
            [None, None, None],
            [("s", "glovo"), ("s", "G-2"), ("s", "2026-11-02")],
        ]
    )
    assert [r.row_number for r in values(data)] == [2, 5]


def test_the_header_row_may_follow_empty_rows() -> None:
    data = build([[[], [None], HEADERS, [("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02")]]])
    assert [r.row_number for r in values(data)] == [4]


def test_a_recognized_header_repeated_rejects_the_file() -> None:
    data = simple([], headers=[*HEADERS, ("s", "Proveedor")])
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(data)
    assert caught.value.reason == "missing_required_header"
    assert "repetido" in (caught.value.detail or "")


def test_headers_are_matched_exactly() -> None:
    data = simple([], headers=[("s", "proveedor"), ("s", "Order ID"), ("s", "Fecha y hora")])
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx(data)
    assert caught.value.detail == "Proveedor"


# --- numbers keep their digits (BE-17, BE-06) -----------------------


@pytest.mark.parametrize("raw", ["-12.5", "0", "12.345", "0.10", "1234567.891", "1.5E-3"])
def test_a_numeric_cell_keeps_the_raw_text_of_the_file(raw: str) -> None:
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02"), ("n", raw)]], headers))
    assert cells["claim_amount"] == Cell("number", raw)


def test_a_text_amount_stays_text_even_if_it_looks_numeric() -> None:
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    for text_value in ("12,50 €", "12.5"):
        cells = one(
            simple(
                [[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02"), ("s", text_value)]], headers
            )
        )
        assert cells["claim_amount"].kind == "text"


def test_an_empty_amount_cell_is_absent() -> None:
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("s", "2026-11-02"), None]], headers))
    assert cells.get("claim_amount", Cell("empty")).kind == "empty"


def test_the_three_amount_cases_of_be_17_through_the_row_rules() -> None:
    headers = [*HEADERS, ("s", "Importe a reclamar")]
    rows = [
        [("s", "glovo"), ("s", f"G-{i}"), ("s", "2026-11-02"), amount]
        for i, amount in enumerate([("n", "-12.5"), ("n", "0"), ("n", "12.345"), ("s", "12,50 €")])
    ]
    results = [read_row(r.cells, BRANCHES) for r in values(simple(rows, headers))]
    assert [str(x.fields.claim_amount) for x in results[:3]] == ["-12.5", "0", "12.345"]
    assert results[3].errors == ("El importe a reclamar debe ser numérico.",)


# --- text -----------------------------------------------------------


def test_shared_and_inline_strings_are_text() -> None:
    cells = one(simple([[("s", "Uber Eats"), ("i", "AB-1029x"), ("s", "2026-11-02")]]))
    assert cells["provider"] == Cell("text", "Uber Eats")
    assert cells["order_id"] == Cell("text", "AB-1029x")


def test_text_keeps_spaces_case_and_line_breaks() -> None:
    cells = one(simple([[("s", "glovo"), ("i", " Ab-1\n "), ("s", "2026-11-02")]]))
    assert cells["order_id"].text == " Ab-1\n "


def test_a_numeric_order_id_cell_stays_a_number() -> None:
    cells = one(simple([[("s", "glovo"), ("n", "100234"), ("s", "2026-11-02")]]))
    assert cells["order_id"].kind == "number"
    assert read_row(cells, BRANCHES).errors == ("El Order ID debe ser texto, no un número.",)


# --- dates (BE-12) --------------------------------------------------


def test_a_native_date_time_cell_is_a_date_time() -> None:
    # 46308.848611111 is 2026-10-12 20:22 in the 1900 system.
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("dt", "46307.84861111111")]]))
    assert cells["when"] == Cell("datetime", when=datetime(2026, 10, 12, 20, 22))


def test_a_native_date_cell_has_no_time() -> None:
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("d", "46307")]]))
    assert cells["when"] == Cell("datetime", when=datetime(2026, 10, 12, 0, 0))


def test_the_1904_date_system_is_honored() -> None:
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("d", "44845")]], date1904=True))
    assert cells["when"].when == datetime(2026, 10, 12, 0, 0)


def test_a_number_with_a_general_format_is_not_a_date() -> None:
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("n", "46307")]]))
    assert cells["when"].kind == "number"


def test_a_date_written_as_text_stays_text() -> None:
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("s", "2026-10-12 20:22")]]))
    assert cells["when"] == Cell("text", "2026-10-12 20:22")


def test_the_three_date_cases_of_be_12_through_the_row_rules() -> None:
    rows = [
        [("s", "glovo"), ("s", "G-1"), ("dt", "46307.84861111111")],
        [("s", "glovo"), ("s", "G-2"), ("d", "46307")],
        [("s", "glovo"), ("s", "G-3"), ("s", "12/10/2026")],
    ]
    first, second, third = (read_row(r.cells, BRANCHES) for r in values(simple(rows)))
    assert (str(first.fields.incident_date), str(first.fields.incident_time)) == (
        "2026-10-12",
        "20:22:00",
    )
    assert (str(second.fields.incident_date), second.fields.incident_time) == ("2026-10-12", None)
    assert not third.valid


# --- formulas, booleans, errors -------------------------------------


def test_a_formula_cell_is_reported_as_a_formula_and_never_evaluated() -> None:
    cells = one(simple([[("s", "glovo"), ("s", "G-1"), ("f", "A1+1", "46307")]]))
    assert cells["when"].kind == "formula"
    assert not read_row(cells, BRANCHES).valid


def test_booleans_and_error_values_are_text_and_fail_validation() -> None:
    cells = one(simple([[("b", "1"), ("e", "#N/A"), ("s", "2026-11-02")]]))
    assert cells["provider"].kind == "text"
    assert not read_row(cells, BRANCHES).valid


# --- the sample files of the repository -----------------------------

SAMPLES = Path(__file__).resolve().parents[4] / "docs" / "samples" / "xlsx"


def test_the_sample_incidencias_file_reads_to_the_documented_classes() -> None:
    sheet = read_xlsx((SAMPLES / "incidencias.xlsx").read_bytes())
    results = [read_row(r.cells, BRANCHES) for r in sheet.rows]
    assert len(results) == 18
    assert sum(1 for r in results if r.valid) == 12
    reasons = [e for r in results for e in r.errors]
    assert len(reasons) == 6


def test_the_sample_only_mandatory_file_has_absent_optionals() -> None:
    sheet = read_xlsx((SAMPLES / "solo-obligatorios.xlsx").read_bytes())
    assert sheet.rows and all(
        r.cells.keys() <= {"provider", "order_id", "when"} for r in sheet.rows
    )


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("sin-order-id.xlsx", "missing_required_header"),
        ("dos-hojas.xlsx", "multiple_worksheets"),
        ("danado.xlsx", "corrupt_or_protected_file"),
    ],
)
def test_the_sample_rejected_files_are_rejected_for_their_reason(name: str, reason: str) -> None:
    with pytest.raises(XlsxRejected) as caught:
        read_xlsx((SAMPLES / name).read_bytes())
    assert caught.value.reason == reason
