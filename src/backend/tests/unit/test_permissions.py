"""Permission matrix (RNF-04, BE-08): the administrator operates, the global manager only reads."""

import pytest

from app.domain.permissions import PERMISSIONS, Permission, permissions_of
from app.domain.roles import ROLES

ALL: set[Permission] = set(PERMISSIONS)
READ_ONLY: set[Permission] = {"incidents_read", "metrics_read"}


def test_the_administrator_has_every_permission() -> None:
    assert set(permissions_of("administrator")) == ALL


def test_the_global_manager_only_reads_incidents_and_the_dashboard() -> None:
    assert set(permissions_of("global_manager")) == READ_ONLY


@pytest.mark.parametrize("role", ROLES)
def test_every_role_has_a_defined_set(role) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(permissions_of(role), tuple)


def test_the_permissions_are_exactly_the_ones_of_the_approved_contract() -> None:
    # The session operation of docs/api/openapi.yaml lists these six names.
    assert set(PERMISSIONS) == {
        "import",
        "confirm",
        "incidents_read",
        "incidents_write",
        "metrics_read",
        "queue_control",
    }


def test_an_unknown_role_has_no_permission() -> None:
    assert permissions_of("intruder") == ()  # type: ignore[arg-type]
