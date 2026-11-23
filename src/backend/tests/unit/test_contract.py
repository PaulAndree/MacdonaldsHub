"""The API against the approved contract (ADR-16, BE-18): a difference blocks the integration."""

import re
from pathlib import Path

import pytest
import yaml
from sqlalchemy import create_engine

from app.adapters.registry import default_registry
from app.api.main import build_app
from app.composition import Container
from app.settings import Settings
from tests.contract.compare import differences, operations
from tests.contract.registry import DEFERRED, NOT_IN_CONTRACT_PREFIXES, PENDING

CONTRACT = Path(__file__).resolve().parents[4] / "docs" / "api" / "openapi.yaml"


@pytest.fixture(scope="module")
def approved() -> dict:  # type: ignore[type-arg]
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def generated() -> dict:  # type: ignore[type-arg]
    settings = Settings(
        _env_file=None,
        app_env="local",
        identity_provider="dev",
        dev_identity_email="dev@example.test",
        storage_backend="azurite",
        storage_connection_string="UseDevelopmentStorage=true",
        mail_transport="smtp_capture",
        telemetry_exporter="console",
        database_url="postgresql+psycopg://u:p@localhost:5432/none",
        frontend_origin="http://localhost:3000",
    )  # type: ignore[arg-type]
    engine = create_engine("postgresql+psycopg://u:p@localhost:5432/none")  # never connects
    app = build_app(settings, Container(settings, default_registry()), engine)
    return app.openapi()


def test_the_approved_contract_is_the_one_in_the_repository(approved) -> None:  # type: ignore[no-untyped-def]
    # The version is whatever the administrator's approval record names, not a number written here.
    record = (CONTRACT.parents[1] / "approvals" / "change_01_frontend.md").read_text(
        encoding="utf-8"
    )
    recorded = re.search(r"<!--\s*approval:\s*contractVersion=(\S+)", record)
    assert recorded is not None, "the approval record has no marker"
    assert approved["info"]["version"] == recorded.group(1)
    assert len(operations(approved)) == 24


def test_every_approved_operation_is_served_pending_or_deferred(approved, generated) -> None:  # type: ignore[no-untyped-def]
    wanted = set(operations(approved))
    served = set(operations(generated))
    unaccounted = wanted - served - set(PENDING) - DEFERRED
    assert not unaccounted, (
        f"approved operations that nothing serves or lists: {sorted(unaccounted)}"
    )


def test_the_lists_do_not_keep_operations_that_are_served(approved, generated) -> None:  # type: ignore[no-untyped-def]
    served = set(operations(generated))
    stale = (set(PENDING) | DEFERRED) & served
    assert not stale, f"served operations still listed as pending or deferred: {sorted(stale)}"


def test_the_lists_only_name_operations_of_the_contract(approved) -> None:  # type: ignore[no-untyped-def]
    wanted = set(operations(approved))
    assert (set(PENDING) | DEFERRED) <= wanted


def test_the_email_queue_belongs_to_change_3(approved) -> None:  # type: ignore[no-untyped-def]
    assert DEFERRED == {"getEmailQueue", "pauseEmailQueue", "resumeEmailQueue"}


def test_the_api_serves_nothing_the_contract_does_not_define(approved, generated) -> None:  # type: ignore[no-untyped-def]
    extra = [
        p
        for p in generated["paths"]
        if p not in approved["paths"] and not p.startswith(NOT_IN_CONTRACT_PREFIXES)
    ]
    assert not extra, f"paths served but not in the approved contract: {extra}"


def test_the_served_operations_match_the_approved_contract(approved, generated) -> None:  # type: ignore[no-untyped-def]
    served = set(operations(generated)) & set(operations(approved))
    assert served, "no approved operation is served yet"
    assert differences(approved, generated, served) == []


def test_a_field_added_by_hand_to_a_served_response_fails_the_contract(approved, generated) -> None:  # type: ignore[no-untyped-def]
    import copy

    changed = copy.deepcopy(generated)
    changed["components"]["schemas"]["Session"]["properties"]["extra"] = {"type": "string"}
    served = set(operations(changed)) & set(operations(approved))
    assert differences(approved, changed, served) == ["getSession: response 200 differs"]
