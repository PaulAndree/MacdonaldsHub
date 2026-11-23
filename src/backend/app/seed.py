"""Explicit command: `python -m app.seed` loads the configured data the application needs.

It ensures the initial administrator on the allowlist (P-07) and the branch catalog (P-01). Both
come from configuration, both are idempotent, and either is skipped when its value is not set.
"""

from sqlalchemy import Engine

from app.adapters.db.allowlist import seed_initial_admin
from app.adapters.db.catalog import seed_branches
from app.adapters.db.engine import make_engine
from app.settings import Settings, load_settings_or_exit


def run(settings: Settings, engine: Engine) -> None:
    identifier = settings.initial_admin_identifier
    if identifier:
        seed_initial_admin(engine, identifier, settings.initial_admin_email)
        print("Initial administrator ensured in the allowlist.")
    else:
        print("No initial administrator configured: allowlist unchanged.")
    names = settings.branch_names
    if names:
        seed_branches(engine, names, deactivate_missing=True)
        print(f"Branch catalog ensured: {len(names)} branches.")
    else:
        print("No BRANCH_CATALOG configured: branch catalog unchanged.")


def main() -> None:
    settings = load_settings_or_exit()
    run(settings, make_engine(settings.database_url.get_secret_value(), settings.database_auth))


if __name__ == "__main__":
    main()
