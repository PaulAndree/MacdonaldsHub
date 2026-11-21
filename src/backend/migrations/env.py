from alembic import context

from app.adapters.db.engine import make_engine

config = context.config
url = config.get_main_option("sqlalchemy.url")
if not url:
    raise RuntimeError(
        "Run migrations through `python -m app.migrate`; no database URL configured."
    )
auth = config.attributes.get("database_auth", "password")


def run_migrations_online() -> None:
    engine = make_engine(url, auth)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
