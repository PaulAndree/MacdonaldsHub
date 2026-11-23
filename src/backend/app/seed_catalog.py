"""Explicit command: `python -m app.seed_catalog` loads the branch catalog from BRANCH_CATALOG."""

from app.adapters.db.catalog import seed_branches
from app.adapters.db.engine import make_engine
from app.settings import load_settings_or_exit


def main() -> None:
    settings = load_settings_or_exit()
    names = settings.branch_names
    if not names:
        raise SystemExit("Nothing to seed: set BRANCH_CATALOG (comma-separated branch names)")
    engine = make_engine(settings.database_url.get_secret_value(), settings.database_auth)
    seed_branches(engine, names, deactivate_missing=True)
    print(f"Branch catalog ensured: {len(names)} branches.")


if __name__ == "__main__":
    main()
