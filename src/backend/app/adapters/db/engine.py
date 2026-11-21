from collections.abc import Callable
from typing import Any, Literal

from sqlalchemy import Engine, create_engine, event, text

DatabaseAuth = Literal["password", "managed_identity"]
# Token audience for Azure Database for PostgreSQL (Microsoft Entra authentication).
POSTGRES_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"
# Tokens last about an hour; recycle pooled connections well before they matter.
_POOL_RECYCLE_SECONDS = 1800

TokenProvider = Callable[[], str]


def managed_identity_token() -> str:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential().get_token(POSTGRES_TOKEN_SCOPE).token


def make_engine(
    url: str,
    auth: DatabaseAuth = "password",
    token_provider: TokenProvider | None = None,
) -> Engine:
    """Create the engine. With managed identity each new connection gets a fresh Entra token."""
    if auth == "password":
        return create_engine(url, pool_pre_ping=True)

    provider = token_provider or _cached_credential_token()
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=_POOL_RECYCLE_SECONDS)

    @event.listens_for(engine, "do_connect")
    def _inject_token(dialect: Any, conn_rec: Any, cargs: Any, cparams: dict[str, Any]) -> None:
        cparams["password"] = provider()

    return engine


def _cached_credential_token() -> TokenProvider:
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()  # created once; it caches tokens until near expiry

    def provider() -> str:
        return credential.get_token(POSTGRES_TOKEN_SCOPE).token

    return provider


def ping(engine: Engine) -> bool:
    """True when PostgreSQL answers a trivial query."""
    with engine.connect() as conn:
        return bool(conn.execute(text("SELECT 1")).scalar_one() == 1)
