"""Catalog configuration (P-01): the branch list comes from configuration, never from the code."""

from app.settings import Settings
from tests.unit.test_settings import BASE, make


def test_imports_are_disabled_by_default() -> None:
    assert make(BASE).imports_enabled is False


def test_the_branch_catalog_is_read_from_a_comma_separated_value() -> None:
    s = make({**BASE, "BRANCH_CATALOG": "Centro, norte ,SUR"})
    # Only provider and branch are lowercased in v1; surrounding blanks around list items are
    # separators, not part of a name.
    assert s.branch_names == ("centro", "norte", "sur")


def test_an_absent_catalog_is_empty_not_invented() -> None:
    assert make(BASE).branch_names == ()


def test_blank_entries_and_repeats_are_ignored() -> None:
    s = make({**BASE, "BRANCH_CATALOG": "centro,, centro ,norte,"})
    assert s.branch_names == ("centro", "norte")


def test_a_settings_object_is_not_given_a_default_catalog() -> None:
    assert Settings.model_fields["branch_catalog"].default is None
