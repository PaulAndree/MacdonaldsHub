"""Offline checks on the compiled Bicep: the security-relevant shape the specs rely on.

Run: python -m pytest infra/tests   (needs the Azure CLI with Bicep: `az bicep install`)
"""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

INFRA = Path(__file__).resolve().parent.parent


def compile_bicep(file: str) -> dict[str, Any]:
    out = subprocess.run(
        ["az", "bicep", "build", "--file", str(INFRA / file), "--stdout"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def main() -> dict[str, Any]:
    return compile_bicep("main.bicep")


def deployments(template: dict[str, Any]) -> dict[str, dict[str, Any]]:
    resources = template["resources"]
    items = resources.values() if isinstance(resources, dict) else resources
    return {r["name"]: r for r in items if r["type"] == "Microsoft.Resources/deployments"}


def param_value(deployment: dict[str, Any], name: str) -> Any:
    value = deployment["properties"]["parameters"][name]
    return value.get("value", value.get("expression"))


def nested_resources(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    resources = deployment["properties"]["template"]["resources"]
    return list(resources.values() if isinstance(resources, dict) else resources)


def role_assignments(main: dict[str, Any]) -> list[tuple[str, str]]:
    """(name expression, resolved role-definition GUID) for every role assignment in any module."""
    found = []
    for deployment in deployments(main).values():
        variables = deployment["properties"]["template"].get("variables", {})
        for r in nested_resources(deployment):
            if r["type"] != "Microsoft.Authorization/roleAssignments":
                continue
            expr = r["properties"]["roleDefinitionId"]
            var = re.search(r"variables\('(\w+)'\)", expr)
            found.append((r["name"], variables[var.group(1)] if var else expr))
    return found


def module(main: dict[str, Any], name: str) -> dict[str, Any]:
    return deployments(main)[name]


def all_text(main: dict[str, Any]) -> str:
    return json.dumps(main)


def test_api_has_internal_ingress_only(main: dict[str, Any]) -> None:  # BASE-11
    assert param_value(module(main, "api"), "ingressMode") == "internal"


def test_worker_has_no_ingress_and_exactly_one_replica(main: dict[str, Any]) -> None:  # RNF-09
    worker = module(main, "worker")
    assert param_value(worker, "ingressMode") == "none"
    assert param_value(worker, "minReplicas") == 1 and param_value(worker, "maxReplicas") == 1


def test_only_the_frontend_is_exposed_to_the_internet(main: dict[str, Any]) -> None:
    modes = {n: param_value(module(main, n), "ingressMode") for n in ("frontend", "api", "worker")}
    assert modes == {"frontend": "external", "api": "internal", "worker": "none"}


def test_easy_auth_exists_once_and_only_on_the_frontend(main: dict[str, Any]) -> None:  # ADR-12
    auth_modules = [
        n for n, d in deployments(main).items()
        if any(r["type"] == "Microsoft.App/containerApps/authConfigs" for r in nested_resources(d))
    ]
    assert auth_modules == ["easy-auth"]
    auth = module(main, "easy-auth")
    assert "frontendAppName" in json.dumps(param_value(auth, "frontendAppName"))
    assert "workerAppName" not in json.dumps(auth) and "apiAppName" not in json.dumps(auth)
    config = nested_resources(auth)[0]["properties"]
    assert config["platform"]["enabled"] is True
    assert config["globalValidation"]["unauthenticatedClientAction"] == "RedirectToLoginPage"
    assert config["globalValidation"]["redirectToProvider"] == "google"
    assert set(config["identityProviders"]) == {"google"}  # no Entra / other login provider


def test_easy_auth_deploys_only_when_enabled(main: dict[str, Any]) -> None:
    condition = module(main, "easy-auth")["condition"]
    assert "easyAuthEnabled" in condition and "deployApps" in condition


def test_identity_headers_are_trusted_only_when_easy_auth_is_enabled(main: dict[str, Any]) -> None:
    env = json.dumps(param_value(module(main, "frontend"), "env"))
    assert "TRUST_EASY_AUTH_HEADERS" in env
    # ARM's string(true) is "True"; the proxy expects lowercase, so it must be lowered explicitly.
    assert "toLower(string(parameters('easyAuthEnabled')))" in env


def test_development_identity_cannot_be_configured_in_azure(main: dict[str, Any]) -> None:  # RNF-16
    text = all_text(main)
    assert "DEV_IDENTITY" not in text
    assert "'dev'" not in text and '"dev"' not in text.replace('"dev-', "")
    assert "easy_auth" in text


def test_every_azure_app_declares_a_non_local_environment(main: dict[str, Any]) -> None:
    assert "'local'" not in all_text(main)
    assert "parameters('environmentName')" in all_text(main)


def test_database_has_no_password_anywhere(main: dict[str, Any]) -> None:  # ADR-15
    text = all_text(main).lower()
    assert "administratorloginpassword" not in text
    assert "adminpassword" not in text
    server = next(
        r for d in deployments(main).values() for r in nested_resources(d)
        if r["type"] == "Microsoft.DBforPostgreSQL/flexibleServers"
    )
    auth = server["properties"]["authConfig"]
    assert auth["passwordAuth"] == "Disabled" and auth["activeDirectoryAuth"] == "Enabled"
    env = json.dumps(param_value(module(main, "api"), "env"))
    assert "managed_identity" in env
    assert not re.search(r"postgresql\+psycopg://[^@']*:[^@']*@", env)  # no user:password@


def test_storage_is_locked_down_and_has_both_containers(main: dict[str, Any]) -> None:  # ADR-14
    resources = [r for d in deployments(main).values() for r in nested_resources(d)]
    account = next(r for r in resources if r["type"] == "Microsoft.Storage/storageAccounts")
    assert account["properties"]["allowSharedKeyAccess"] is False
    assert account["properties"]["allowBlobPublicAccess"] is False
    assert account["properties"]["minimumTlsVersion"] == "TLS1_2"
    container_names = [
        r["name"] for r in resources
        if r["type"] == "Microsoft.Storage/storageAccounts/blobServices/containers"
    ]
    assert len(container_names) == 2
    assert sum("'uploads'" in n for n in container_names) == 1
    assert sum("'confirmed'" in n for n in container_names) == 1
    confirmed = next(
        r for r in resources
        if r["type"].endswith("/containers") and "'confirmed'" in r["name"]
    )
    assert confirmed["properties"]["immutableStorageWithVersioning"]["enabled"] is True


def test_no_identity_can_delete_in_confirmed_and_the_worker_can_create_there(  # P-05, ADR-14
    main: dict[str, Any],
) -> None:
    on_confirmed = [role for name, role in role_assignments(main) if "'confirmed'" in name]
    reader = "2a2b9908-6ea1-4ae2-8e65-a410df84e7d1"  # Storage Blob Data Reader
    contributor = "ba92f5b4-2d11-453d-a403-e96b0029c9fe"  # Storage Blob Data Contributor
    assert sorted(on_confirmed) == sorted([reader, contributor])
    # The contributor role includes delete, so exactly one assignment on `confirmed` carries a
    # condition that removes it; the read-only one needs none.
    conditions = [
        r["properties"]["condition"]
        for d in deployments(main).values()
        for r in nested_resources(d)
        if r["type"] == "Microsoft.Authorization/roleAssignments"
        and "'confirmed'" in r["name"]
        and "condition" in r["properties"]
    ]
    assert len(conditions) == 1
    assert "blobs/delete" in conditions[0] and conditions[0].startswith("(!(ActionMatches")


def test_cors_allows_only_the_frontend_origin(main: dict[str, Any]) -> None:
    resources = [r for d in deployments(main).values() for r in nested_resources(d)]
    blob = next(r for r in resources if r["type"] == "Microsoft.Storage/storageAccounts/blobServices")
    rule = blob["properties"]["cors"]["corsRules"][0]
    assert rule["allowedOrigins"] == ["[parameters('frontendOrigin')]"]
    assert set(rule["allowedMethods"]) == {"PUT", "OPTIONS"}


def test_key_vault_is_rbac_only_and_apps_only_read_secrets(main: dict[str, Any]) -> None:  # RNF-04
    resources = [r for d in deployments(main).values() for r in nested_resources(d)]
    vault = next(r for r in resources if r["type"] == "Microsoft.KeyVault/vaults")
    assert vault["properties"]["enableRbacAuthorization"] is True
    assert vault["properties"]["enableSoftDelete"] is True
    vault_roles = [role for name, role in role_assignments(main) if "Microsoft.KeyVault" in name]
    assert vault_roles and set(vault_roles) == {"4633458b-17de-408a-b874-0445c86b69e6"}  # Secrets User


def test_no_secret_values_are_in_the_template(main: dict[str, Any]) -> None:
    text = all_text(main)
    for needle in ("AccountKey=", "InstrumentationKey=", "client_secret", "BEGIN PRIVATE KEY"):
        assert needle not in text
    # The Google client secret is only ever a Key Vault reference.
    assert "secrets/google-client-secret" in text


def test_migrations_run_as_an_explicit_job_not_at_startup(main: dict[str, Any]) -> None:
    job = module(main, "migrate-job")
    assert param_value(job, "command") == ["python", "-m", "app.migrate", "upgrade"]
    assert "Manual" in json.dumps(nested_resources(job))


def test_registry_has_no_admin_user(main: dict[str, Any]) -> None:
    registry = next(
        r for d in deployments(main).values() for r in nested_resources(d)
        if r["type"] == "Microsoft.ContainerRegistry/registries"
    )
    assert registry["properties"]["adminUserEnabled"] is False


def test_environment_isolation_in_naming_and_parameters() -> None:  # BASE-10
    test = (INFRA / "main.test.bicepparam").read_text()
    prod = (INFRA / "main.prod.bicepparam").read_text()
    assert "param environmentName = 'test'" in test
    assert "param environmentName = 'production'" in prod
    template = (INFRA / "main.bicep").read_text()
    # Every stateful resource name is derived from the environment and the resource group.
    for fragment in ("prefix", "envShort", "uniqueString(resourceGroup().id)"):
        assert fragment in template
    for resource in ("registryName:", "vaultName:", "storageName:", "serverName:"):
        line = next(ln for ln in template.splitlines() if resource in ln)
        assert "envShort" in line or "prefix" in line, line


def test_pending_decisions_have_no_invented_defaults() -> None:  # P-07
    template = (INFRA / "main.bicep").read_text()
    assert "param allowlistIdentifier string = ''" in template
    for f in ("main.test.bicepparam", "main.prod.bicepparam"):
        text = (INFRA / f).read_text()
        assert "readEnvironmentVariable('ALLOWLIST_IDENTIFIER', '')" in text
        assert "readEnvironmentVariable('GOOGLE_CLIENT_ID', '')" in text


def test_the_branch_catalog_has_no_invented_default_and_imports_start_off() -> None:  # P-01
    template = (INFRA / "main.bicep").read_text()
    assert "param branchCatalog string = ''" in template
    assert "param importsEnabled bool = false" in template
    assert "param testRecipientEmail string = ''" in template
    for f in ("main.test.bicepparam", "main.prod.bicepparam"):
        text = (INFRA / f).read_text()
        assert "readEnvironmentVariable('BRANCH_CATALOG', '')" in text
        assert "readEnvironmentVariable('IMPORTS_ENABLED', 'false')" in text
        assert "readEnvironmentVariable('TEST_RECIPIENT_EMAIL', '')" in text  # P-01


def test_initial_admin_is_seeded_by_an_explicit_job(main: dict[str, Any]) -> None:  # BASE-03
    job = module(main, "seed-job")
    assert param_value(job, "command") == ["python", "-m", "app.seed"]
    assert "Manual" in json.dumps(nested_resources(job))
