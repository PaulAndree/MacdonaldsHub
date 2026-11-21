import base64
import json
from typing import Any

from app.adapters.identity.dev import DevIdentityProvider
from app.adapters.identity.easy_auth import EasyAuthIdentityProvider

EMAIL_CLAIM = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"


def principal(auth_typ: str = "google", **extra: Any) -> str:
    body = {
        "auth_typ": auth_typ,
        "claims": [{"typ": EMAIL_CLAIM, "val": "ana@example.test"}],
        **extra,
    }
    return base64.b64encode(json.dumps(body).encode()).decode()


def headers(**over: str) -> dict[str, str]:
    base = {
        "x-ms-client-principal": principal(),
        "x-ms-client-principal-id": "google-sub-123",
        "x-ms-client-principal-idp": "google",
    }
    return {**base, **over}


def test_dev_identity_acts_with_configured_role() -> None:
    for role in ("administrator", "global_manager"):
        identity = DevIdentityProvider("dev@example.test", role).resolve({})  # type: ignore[arg-type]
        assert identity is not None
        assert identity.preauthorized_role == role
        assert identity.email == "dev@example.test"


def test_dev_identity_ignores_forged_easy_auth_headers() -> None:
    identity = DevIdentityProvider("dev@example.test", "global_manager").resolve(headers())
    assert identity is not None
    assert identity.email == "dev@example.test"
    assert identity.subject != "google-sub-123"


def test_easy_auth_valid_principal() -> None:
    identity = EasyAuthIdentityProvider().resolve(headers())
    assert identity is not None
    assert identity.subject == "google-sub-123"
    assert identity.email == "ana@example.test"
    assert identity.preauthorized_role is None


def test_easy_auth_missing_principal_is_unauthenticated() -> None:
    assert EasyAuthIdentityProvider().resolve({}) is None
    assert EasyAuthIdentityProvider().resolve({"x-ms-client-principal-id": "x"}) is None


def test_easy_auth_malformed_principal_is_unauthenticated() -> None:
    p = EasyAuthIdentityProvider()
    assert p.resolve(headers(**{"x-ms-client-principal": "!!!not-base64!!!"})) is None
    not_json = base64.b64encode(b"plain text").decode()
    assert p.resolve(headers(**{"x-ms-client-principal": not_json})) is None
    a_list = base64.b64encode(b"[1,2]").decode()
    assert p.resolve(headers(**{"x-ms-client-principal": a_list})) is None


def test_easy_auth_rejects_non_google_identity_provider() -> None:
    p = EasyAuthIdentityProvider()
    assert p.resolve(headers(**{"x-ms-client-principal": principal(auth_typ="aad")})) is None
    assert p.resolve(headers(**{"x-ms-client-principal-idp": "aad"})) is None


def test_easy_auth_principal_without_any_identifier_is_unauthenticated() -> None:
    empty = base64.b64encode(json.dumps({"auth_typ": "google", "claims": []}).encode()).decode()
    assert EasyAuthIdentityProvider().resolve({"x-ms-client-principal": empty}) is None
