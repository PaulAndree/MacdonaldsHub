"""Exclusive classification of rows (RN-01..RN-03, RF-04): E-03, E-04, BE-01, BE-06, BE-13."""

from datetime import date, time
from decimal import Decimal

from app.domain.classification import Existing, SourceRow, classify
from app.domain.rows import Fields, RowResult

D = Decimal


def fields(provider="uber eats", order_id="A-1", **over):  # type: ignore[no-untyped-def]
    base = dict(
        provider=provider,
        order_id=order_id,
        incident_date=date(2026, 11, 2),
        incident_time=time(12, 15),
        branch="centro",
        claim_amount=D("12.50"),
        provider_costs=None,
        total=None,
        description=None,
    )
    return Fields(**{**base, **over})


def src(number: int, **over) -> SourceRow:  # type: ignore[no-untyped-def]
    return SourceRow(number, RowResult(fields(**over), ()))


def bad(number: int, *reasons: str) -> SourceRow:
    return SourceRow(number, RowResult(Fields(), tuple(reasons)))


def existing(**over) -> Existing:  # type: ignore[no-untyped-def]
    f = fields(**over)
    return Existing("inc-1", f)


def classes(rows, current=None):  # type: ignore[no-untyped-def]
    return [(c.row_number, c.row_class) for c in classify(rows, current or {})]


KEY = ("uber eats", "A-1")


# --- one class per row, errors first -------------------------------------------------------------


def test_a_valid_row_without_match_is_new() -> None:
    assert classes([src(2)]) == [(2, "new")]


def test_an_invalid_row_is_an_error_with_its_reasons() -> None:
    (c,) = classify([bad(2, "Falta el Order ID.", "Fecha mala.")], {})
    assert c.row_class == "error"
    assert c.reason == "Falta el Order ID. Fecha mala."


def test_every_row_gets_exactly_one_class_in_file_order() -> None:
    rows = [src(2), bad(3, "x"), src(4, order_id="B-2"), src(5, order_id="B-2")]
    result = classify(rows, {})
    assert [c.row_number for c in result] == [2, 3, 4, 5]
    assert {c.row_class for c in result} <= {"new", "duplicate", "conflict", "error"}


def test_an_error_row_does_not_take_part_in_key_groups() -> None:
    # The invalid row cannot make its valid namesake a duplicate: it has no readable key.
    rows = [src(2), bad(3, "x")]
    assert classes(rows) == [(2, "new"), (3, "error")]


# --- against existing incidents (E-03, E-04) ------------------------------------------------------


def test_same_key_and_same_fields_as_an_existing_incident_is_a_duplicate() -> None:
    (c,) = classify([src(2)], {KEY: existing()})
    assert c.row_class == "duplicate"
    assert c.reason == "Ya existe una incidencia con la misma clave y los mismos datos."
    assert c.existing_id == "inc-1"


def test_same_key_with_a_different_field_is_a_conflict_with_both_versions_available() -> None:
    (c,) = classify([src(2, claim_amount=D("99"))], {KEY: existing()})
    assert c.row_class == "conflict"
    assert c.reason == "Ya existe una incidencia con la misma clave pero con datos distintos."
    assert c.existing_id == "inc-1"


def test_the_key_includes_the_provider() -> None:
    other = {("just eat", "A-1"): existing(provider="just eat")}
    assert classes([src(2)], other) == [(2, "new")]


def test_the_branch_is_not_part_of_the_key_but_is_a_relevant_field() -> None:
    assert classes([src(2, branch="norte")], {KEY: existing()}) == [(2, "conflict")]


# --- repetitions inside the file (BE-01) -----------------------------------------------


def test_identical_repetitions_are_all_duplicates_and_none_is_chosen() -> None:
    result = classify([src(2), src(3), src(4)], {})
    assert [c.row_class for c in result] == ["duplicate"] * 3
    assert result[0].reason.startswith(
        "La clave aparece repetida en el archivo con los mismos datos"
    )
    assert all(c.existing_id is None for c in result)


def test_repetitions_with_different_data_are_all_conflicts() -> None:
    result = classify([src(2), src(3, claim_amount=D("15"))], {})
    assert [c.row_class for c in result] == ["conflict", "conflict"]
    assert "datos distintos" in result[0].reason


def test_a_conflict_prevails_over_a_duplicate_in_the_same_group() -> None:
    rows = [src(2), src(3), src(4, description="otra")]
    assert classes(rows) == [(2, "conflict"), (3, "conflict"), (4, "conflict")]


def test_repetitions_equal_to_the_existing_incident_are_duplicates() -> None:
    assert classes([src(2), src(3)], {KEY: existing()}) == [(2, "duplicate"), (3, "duplicate")]


def test_repetitions_where_one_differs_from_the_existing_incident_are_all_conflicts() -> None:
    rows = [src(2), src(3, claim_amount=D("1"))]
    result = classify(rows, {KEY: existing()})
    assert [c.row_class for c in result] == ["conflict", "conflict"]
    assert (
        result[1].reason == "Ya existe una incidencia con la misma clave pero con datos distintos."
    )
    # The row that equals the existing incident still explains why it is excluded.
    assert "datos distintos" in result[0].reason


def test_groups_are_independent() -> None:
    rows = [
        src(2),
        src(3),
        src(4, order_id="B-1"),
        src(5, order_id="C-1"),
        src(6, order_id="C-1", total=D("1")),
    ]
    assert classes(rows) == [
        (2, "duplicate"),
        (3, "duplicate"),
        (4, "new"),
        (5, "conflict"),
        (6, "conflict"),
    ]


# --- relevant fields (RN-02, BE-06, BE-13) ---------------------------------------------


def test_amounts_are_compared_by_value_and_not_by_how_they_were_written() -> None:
    assert classes([src(2, claim_amount=D("12.5"))], {KEY: existing(claim_amount=D("12.50"))}) == [
        (2, "duplicate")
    ]


def test_a_more_precise_amount_is_a_difference() -> None:
    assert classes([src(2, claim_amount=D("12.501"))], {KEY: existing()}) == [(2, "conflict")]


def test_an_absent_amount_is_not_equal_to_zero() -> None:
    assert classes([src(2, claim_amount=None)], {KEY: existing(claim_amount=D("0"))}) == [
        (2, "conflict")
    ]
    assert classes([src(2, claim_amount=D("0"))], {KEY: existing(claim_amount=None)}) == [
        (2, "conflict")
    ]


def test_an_absent_optional_value_equals_an_absent_one() -> None:
    same = existing(branch=None, claim_amount=None, description=None)
    assert classes([src(2, branch=None, claim_amount=None, description=None)], {KEY: same}) == [
        (2, "duplicate")
    ]


def test_with_and_without_time_is_a_conflict() -> None:
    assert classes([src(2, incident_time=None)], {KEY: existing()}) == [(2, "conflict")]


def test_a_different_time_is_a_conflict() -> None:
    assert classes([src(2, incident_time=time(12, 16))], {KEY: existing()}) == [(2, "conflict")]


def test_midnight_is_not_the_same_as_no_time() -> None:
    assert classes([src(2, incident_time=time(0, 0))], {KEY: existing(incident_time=None)}) == [
        (2, "conflict")
    ]


def test_a_different_date_is_a_conflict() -> None:
    assert classes([src(2, incident_date=date(2026, 11, 3))], {KEY: existing()}) == [
        (2, "conflict")
    ]


def test_the_description_is_compared_exactly() -> None:
    assert classes([src(2, description="a ")], {KEY: existing(description="a")}) == [
        (2, "conflict")
    ]


def test_the_age_of_the_incident_never_excludes_a_row() -> None:
    assert classes([src(2, incident_date=date(2001, 1, 1))]) == [(2, "new")]
