"""Fixtures shared by the integration tests."""

import pytest
from sqlalchemy import text

from app.adapters.db.catalog import seed_branches
from tests.integration.batch_helpers import ADMIN
from tests.integration.test_api import azure_like_settings, client_for, reset


@pytest.fixture
def client(database_url: str, azurite_connection_string: str):  # type: ignore[no-untyped-def]
    reset(database_url)
    test_client, engine = client_for(
        azure_like_settings(database_url, azurite_connection_string), database_url
    )
    seed_branches(engine, ("centro", "norte", "sur"))
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO allowlist_entry (id, identifier, email, role) "
                "VALUES (gen_random_uuid(), :a, :a, 'administrator')"
            ),
            {"a": ADMIN},
        )
    test_client.engine = engine  # type: ignore[attr-defined]
    # The only recipient allowed until the real ones exist (P-01): a test address.
    test_client.app.state.settings.test_recipient_email = "test-recipient@example.test"
    yield test_client
    engine.dispose()
