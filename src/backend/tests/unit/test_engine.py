from typing import Any

from app.adapters.db.engine import make_engine


def fire_do_connect(engine: Any) -> dict[str, Any]:
    cparams: dict[str, Any] = {"user": "app-identity", "host": "h"}
    engine.dialect.dispatch.do_connect(engine.dialect, None, [], cparams)
    return cparams


def test_managed_identity_injects_a_fresh_token_as_the_password() -> None:
    tokens = iter(["token-1", "token-2"])
    engine = make_engine(
        "postgresql+psycopg://app-identity@server.postgres.database.azure.com/db",
        "managed_identity",
        token_provider=lambda: next(tokens),
    )
    assert fire_do_connect(engine)["password"] == "token-1"
    assert fire_do_connect(engine)["password"] == "token-2"  # per connection, never cached here
    assert engine.pool._recycle <= 1800  # pooled connections are recycled before tokens expire


def test_managed_identity_url_carries_no_password() -> None:
    url = "postgresql+psycopg://app-identity@server.postgres.database.azure.com/db"
    engine = make_engine(url, "managed_identity", token_provider=lambda: "t")
    assert engine.url.password is None


def test_password_auth_does_not_touch_credentials() -> None:
    engine = make_engine("postgresql+psycopg://u:p@localhost/db")
    cparams = fire_do_connect(engine)
    assert "password" not in cparams
