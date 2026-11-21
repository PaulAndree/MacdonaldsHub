"""Identity forwarded by Container Apps Easy Auth (Google), trusted only outside local.

The API is reachable only through the frontend proxy (internal ingress) and Easy Auth
overwrites these headers at the edge, so their presence is the authentication signal.
"""

import base64
import binascii
import json
from typing import Any

from app.services.ports import Identity

PRINCIPAL = "x-ms-client-principal"
PRINCIPAL_ID = "x-ms-client-principal-id"
PRINCIPAL_NAME = "x-ms-client-principal-name"
PRINCIPAL_IDP = "x-ms-client-principal-idp"

_EMAIL_CLAIMS = {
    "email",
    "emails",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
}


class EasyAuthIdentityProvider:
    def resolve(self, headers: dict[str, str]) -> Identity | None:
        raw = headers.get(PRINCIPAL)
        if not raw:
            return None
        principal = self._decode(raw)
        if principal is None or principal.get("auth_typ") != "google":
            return None
        if headers.get(PRINCIPAL_IDP, "google").lower() != "google":
            return None
        subject = headers.get(PRINCIPAL_ID) or None
        email = self._email(principal) or headers.get(PRINCIPAL_NAME) or None
        if subject is None and email is None:
            return None
        return Identity(subject=subject, email=email)

    @staticmethod
    def _decode(raw: str) -> dict[str, Any] | None:
        try:
            decoded = json.loads(base64.b64decode(raw, validate=True))
        except (binascii.Error, ValueError):
            return None
        return decoded if isinstance(decoded, dict) else None

    @staticmethod
    def _email(principal: dict[str, Any]) -> str | None:
        claims = principal.get("claims")
        if not isinstance(claims, list):
            return None
        for claim in claims:
            if isinstance(claim, dict) and claim.get("typ") in _EMAIL_CLAIMS:
                val = claim.get("val")
                if isinstance(val, str) and val:
                    return val
        return None
