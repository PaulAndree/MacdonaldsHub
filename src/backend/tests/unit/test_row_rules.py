"""Row rules of the XLSX input (RF-06, RN-06, RN-09, RN-10): E-05, BE-06, BE-12, BE-14, BE-17."""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from app.domain.rows import (
    EMPTY,
    Cell,
    is_blank,
    missing_mandatory_headers,
    read_row,
    text,
)

BRANCHES = frozenset({"centro", "norte"})


def number(raw: str) -> Cell:
    return Cell("number", raw)


def native(value: datetime) -> Cell:
    return Cell("datetime", when=value)


def row(**cells: Cell):  # type: ignore[no-untyped-def]
    """A valid row with the given cells replaced."""
    base = {
        "provider": text("uber eats"),
        "order_id": text("UE-1"),
        "when": native(datetime(2026, 11, 2, 12, 15)),
    }
    return read_row({**base, **cells}, BRANCHES)


# --- mandatory values -------------------------------------------------------------------------


def test_a_row_with_only_the_three_mandatory_values_is_valid_with_optionals_absent() -> None:
    result = row()
    assert result.valid and result.errors == ()
    f = result.fields
    assert (f.provider, f.order_id) == ("uber eats", "UE-1")
    assert (f.branch, f.claim_amount, f.provider_costs, f.total, f.description) == (None,) * 5


@pytest.mark.parametrize("name", ["provider", "order_id", "when"])
def test_a_missing_mandatory_value_invalidates_the_row(name: str) -> None:
    result = row(**{name: EMPTY})
    assert not result.valid
    assert len(result.errors) == 1 and result.errors[0].startswith("Falta")


def test_one_bad_row_reports_every_problem_it_has() -> None:
    result = row(provider=text("rappi"), order_id=EMPTY)
    assert len(result.errors) == 2


# --- provider and branch: only these are lowercased --------------------------------------------


def test_the_provider_is_lowercased() -> None:
    assert row(provider=text("Uber Eats")).fields.provider == "uber eats"
    assert row(provider=text("GLOVO")).fields.provider == "glovo"


def test_an_unknown_provider_is_a_row_error() -> None:
    result = row(provider=text("rappi"))
    assert result.errors == ("El proveedor «rappi» no es uno de los conocidos.",)


def test_the_provider_is_not_trimmed_or_given_aliases() -> None:
    assert not row(provider=text(" uber eats")).valid
    assert not row(provider=text("ubereats")).valid


def test_the_order_id_is_kept_exactly() -> None:
    for value in ("AB-1029x", "ab-1", " AB-1 ", "00123", "x\ny"):
        assert row(order_id=text(value)).fields.order_id == value


# --- E-05 and BE-14 ----------------------------------------------------------------------------


def test_a_missing_branch_is_valid_and_a_known_one_is_lowercased() -> None:
    assert row(branch=EMPTY).valid
    assert row(branch=EMPTY).fields.branch is None
    assert row(branch=text("Centro")).fields.branch == "centro"


def test_a_branch_that_is_not_in_the_catalog_is_an_error() -> None:
    result = row(branch=text("playa"))
    assert result.errors == ("La sucursal «playa» no es una sucursal conocida.",)


def test_a_numeric_order_id_is_an_error_and_a_text_one_is_kept() -> None:
    assert row(order_id=text("AB-1029x")).fields.order_id == "AB-1029x"
    bad = row(order_id=number("100234"))
    assert bad.errors == ("El Order ID debe ser texto, no un número.",)


# --- BE-17 and BE-06: amounts -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-12.5", "-12.5"),
        ("0", "0"),
        ("12.345", "12.345"),
        ("0.10", "0.10"),
        ("1234567.891", "1234567.891"),
    ],
)
def test_numeric_amounts_keep_sign_and_digits(raw: str, expected: str) -> None:
    amount = row(claim_amount=number(raw)).fields.claim_amount
    assert amount == Decimal(expected)
    assert str(amount) == expected  # the digits typed, with no rounding to two decimals


def test_an_amount_written_in_scientific_notation_keeps_its_value() -> None:
    assert row(total=number("1.5E-3")).fields.total == Decimal("0.0015")


@pytest.mark.parametrize("value", ["12,50 €", "12.5", "doce"])
def test_a_text_amount_is_an_error_even_if_it_looks_numeric(value: str) -> None:
    result = row(claim_amount=text(value))
    assert result.errors == ("El importe a reclamar debe ser numérico.",)


def test_each_amount_column_names_itself_in_the_error() -> None:
    assert "costos de proveedor" in row(provider_costs=text("x")).errors[0]
    assert "total" in row(total=text("x")).errors[0]


def test_an_empty_amount_is_absent_not_zero() -> None:
    f = row(claim_amount=EMPTY, provider_costs=EMPTY, total=EMPTY).fields
    assert (f.claim_amount, f.provider_costs, f.total) == (None, None, None)
    assert row(claim_amount=number("0")).fields.claim_amount == Decimal(0)  # a real zero stays


def test_total_is_not_checked_against_the_other_amounts() -> None:
    # The relation between Total and the other amounts is pending P-10: nothing is validated.
    assert row(claim_amount=number("10"), provider_costs=number("5"), total=number("1")).valid


# --- BE-12: date and time ------------------------------------------------------------------------


def test_a_native_date_time_keeps_date_and_time() -> None:
    f = row(when=native(datetime(2026, 10, 12, 20, 22))).fields
    assert (f.incident_date, f.incident_time) == (date(2026, 10, 12), time(20, 22))


def test_a_native_date_at_midnight_is_a_date_without_time() -> None:
    f = row(when=native(datetime(2026, 10, 12, 0, 0))).fields
    assert (f.incident_date, f.incident_time) == (date(2026, 10, 12), None)


def test_a_date_only_text_has_no_time_and_a_text_with_00_00_keeps_it() -> None:
    assert row(when=text("2026-10-12")).fields.incident_time is None
    f = row(when=text("2026-10-12 00:00")).fields
    assert (f.incident_date, f.incident_time) == (date(2026, 10, 12), time(0, 0))
    f = row(when=text("2026-10-12 20:22")).fields
    assert (f.incident_date, f.incident_time) == (date(2026, 10, 12), time(20, 22))


@pytest.mark.parametrize(
    "value",
    [
        "12/10/2026",
        "2026-10-12T20:22",
        "2026-10-12 20:22:10",
        "2026-10-12 8:05",
        " 2026-10-12",
        "2026-13-01",
        "2026-02-30",
        "2026-10-12 24:00",
        "2026-10-12 12:60",
        "hoy",
    ],
)
def test_any_other_date_text_is_a_row_error(value: str) -> None:
    result = row(when=text(value))
    assert not result.valid
    assert "formato" in result.errors[0]


def test_a_number_that_is_not_a_date_is_an_error() -> None:
    assert not row(when=number("46000")).valid


def test_seconds_of_a_native_cell_are_dropped_to_minute_precision() -> None:
    f = row(when=native(datetime(2026, 10, 12, 20, 22, 45))).fields
    assert f.incident_time == time(20, 22)


def test_a_local_time_that_does_not_exist_is_kept_as_given() -> None:
    # 2026-03-29 02:30 does not exist in Europe/Madrid. The time is local wall-clock time, never
    # converted to an instant, so it is stored as typed (P-09).
    f = row(when=text("2026-03-29 02:30")).fields
    assert (f.incident_date, f.incident_time) == (date(2026, 3, 29), time(2, 30))


# --- description and formulas ---------------------------------------------------------------------


def test_a_description_keeps_line_breaks_and_special_characters() -> None:
    value = 'Falta "bebida"\nsin hielo; 100% <b>&'
    assert row(description=text(value)).fields.description == value


def test_an_empty_description_is_absent() -> None:
    assert row(description=EMPTY).fields.description is None


@pytest.mark.parametrize(
    "name", ["provider", "order_id", "when", "branch", "claim_amount", "description"]
)
def test_a_formula_in_any_cell_makes_the_row_an_error(name: str) -> None:
    result = row(**{name: Cell("formula")})
    assert not result.valid
    assert any("fórmula" in e for e in result.errors)


# --- structure helpers ---------------------------------------------------------------------------


def test_a_completely_empty_row_is_blank() -> None:
    assert is_blank({"provider": EMPTY, "order_id": EMPTY})
    assert is_blank({})
    assert not is_blank({"provider": EMPTY, "description": text("x")})


def test_missing_mandatory_headers_are_listed() -> None:
    assert missing_mandatory_headers(["Proveedor", "Order ID", "Fecha y hora", "Total"]) == []
    assert missing_mandatory_headers(["Proveedor", "Fecha y hora"]) == ["Order ID"]
    assert missing_mandatory_headers(["Sucursal"]) == ["Proveedor", "Order ID", "Fecha y hora"]


def test_headers_are_matched_exactly() -> None:
    assert missing_mandatory_headers(["proveedor", "Order ID", "Fecha y hora"]) == ["Proveedor"]
