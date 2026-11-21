"""Explicit command: `python -m app.seed_admin` seeds the initial administrator."""

from pydantic import ValidationError

from app.adapters.db.allowlist import seed_initial_admin
from app.adapters.db.engine import make_engine
from app.settings import load_settings_or_exit


def main() -> None:
    settings = load_settings_or_exit()
    identifier = settings.initial_admin_identifier
    if not identifier:
        raise SystemExit(
            "Nothing to seed: set the INITIAL_ADMIN value matching ALLOWLIST_IDENTIFIER"
        )
    engine = make_engine(settings.database_url.get_secret_value(), settings.database_auth)
    try:
        seed_initial_admin(engine, identifier, settings.initial_admin_email)
    except ValidationError as exc:  # pragma: no cover
        raise SystemExit(str(exc)) from None
    print("Initial administrator ensured in the allowlist.")


if __name__ == "__main__":
    main()
