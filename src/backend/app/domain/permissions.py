"""Permission matrix (RNF-04): which role may do what. Pure rules, no I/O.

The names are the ones of the approved API contract (the `session` operation), so the interface
and the API agree. The API checks them on every operation; hiding a button is only a convenience.
"""

from typing import Literal

from app.domain.roles import Role

Permission = Literal[
    "import",
    "confirm",
    "incidents_read",
    "incidents_write",
    "metrics_read",
    "queue_control",
]

PERMISSIONS: tuple[Permission, ...] = (
    "import",
    "confirm",
    "incidents_read",
    "incidents_write",
    "metrics_read",
    "queue_control",
)

_BY_ROLE: dict[Role, tuple[Permission, ...]] = {
    "administrator": PERMISSIONS,
    # The global manager, if enabled (P-07), only consults incidents, history and the dashboard.
    "global_manager": ("incidents_read", "metrics_read"),
}


def permissions_of(role: Role) -> tuple[Permission, ...]:
    """Permissions of a role; an unknown role has none (deny by default)."""
    return _BY_ROLE.get(role, ())


def can(role: Role, permission: Permission) -> bool:
    return permission in permissions_of(role)
