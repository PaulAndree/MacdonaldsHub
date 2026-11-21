import os

import pytest
from sqlalchemy.engine import make_url


def _required(name: str, what: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    message = f"{name} not set (integration test needs real {what})"
    if os.environ.get("REQUIRE_INTEGRATION"):
        # CI sets REQUIRE_INTEGRATION=1 so a missing service fails instead of silently skipping.
        pytest.fail(message)
    pytest.skip(message)


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _required("TEST_DATABASE_URL", "PostgreSQL")
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        # Integration tests DROP SCHEMA public; never let them touch a real database.
        pytest.fail(f"Refusing to run: TEST_DATABASE_URL database '{name}' must end with '_test'")
    return url


@pytest.fixture(scope="session")
def azurite_connection_string() -> str:
    return _required("TEST_AZURITE_CONNECTION_STRING", "Azurite")


@pytest.fixture(scope="session")
def mailpit() -> tuple[str, int, str]:
    """(smtp host, smtp port, http api base url) of the SMTP capture service."""
    base = _required("TEST_MAILPIT_URL", "Mailpit SMTP capture")
    host = os.environ.get("TEST_SMTP_HOST", "127.0.0.1")
    port = int(os.environ.get("TEST_SMTP_PORT", "1025"))
    return host, port, base.rstrip("/")
