from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from jose.exceptions import JWTError

from eve_craft.platform.auth.domain.models import EsiClientRegistration, SsoMetadata

ACCEPTED_ISSUERS = ("login.eveonline.com", "https://login.eveonline.com", "https://login.eveonline.com/")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class TokenExchangePayload:
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int


class EveSsoClient:
    def __init__(
        self,
        metadata_url: str,
        user_agent: str,
        timeout_seconds: int = 30,
        metadata_cache_ttl_seconds: int = 300,
    ) -> None:
        self._metadata_url = metadata_url
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._metadata_cache_ttl_seconds = metadata_cache_ttl_seconds
        self._metadata_cache: tuple[SsoMetadata, datetime] | None = None
        self._jwks_cache: tuple[dict[str, Any], datetime] | None = None

    def fetch_metadata(self) -> SsoMetadata:
        cached = self._metadata_cache
        if cached is not None and cached[1] > _utc_now():
            return cached[0]

        payload = self._request_json("GET", self._metadata_url)
        metadata = SsoMetadata(
            issuer=str(payload["issuer"]),
            authorization_endpoint=str(payload["authorization_endpoint"]),
            token_endpoint=str(payload["token_endpoint"]),
            jwks_uri=str(payload["jwks_uri"]),
            revocation_endpoint=str(payload.get("revocation_endpoint") or payload.get("revocation_endpoint_url")),
        )
        self._metadata_cache = (
            metadata,
            _utc_now() + timedelta(seconds=self._metadata_cache_ttl_seconds),
        )
        return metadata

    def generate_pkce_pair(self) -> tuple[str, str]:
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    def exchange_code(
        self,
        registration: EsiClientRegistration,
        authorization_code: str,
        code_verifier: str | None,
    ) -> TokenExchangePayload:
        metadata = self.fetch_metadata()
        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": registration.callback_url,
        }
        headers = self._form_headers()

        if code_verifier:
            payload["client_id"] = registration.client_id
            payload["code_verifier"] = code_verifier
        else:
            self._apply_basic_auth(registration, headers)

        response = self._request_json("POST", metadata.token_endpoint, payload=payload, headers=headers)
        return TokenExchangePayload(
            access_token=str(response["access_token"]),
            refresh_token=response.get("refresh_token"),
            token_type=str(response.get("token_type", "Bearer")),
            expires_in=int(response["expires_in"]),
        )

    def refresh_token(
        self,
        registration: EsiClientRegistration,
        refresh_token: str,
    ) -> TokenExchangePayload:
        metadata = self.fetch_metadata()
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        headers = self._form_headers()

        if registration.client_secret:
            self._apply_basic_auth(registration, headers)
        else:
            payload["client_id"] = registration.client_id

        response = self._request_json("POST", metadata.token_endpoint, payload=payload, headers=headers)
        return TokenExchangePayload(
            access_token=str(response["access_token"]),
            refresh_token=response.get("refresh_token", refresh_token),
            token_type=str(response.get("token_type", "Bearer")),
            expires_in=int(response["expires_in"]),
        )

    def revoke_token(self, registration: EsiClientRegistration, token: str) -> None:
        metadata = self.fetch_metadata()
        if metadata.revocation_endpoint is None:
            return

        headers = self._form_headers()
        if registration.client_secret:
            self._apply_basic_auth(registration, headers)

        payload = {"token": token}
        if not registration.client_secret:
            payload["client_id"] = registration.client_id

        self._request_raw("POST", metadata.revocation_endpoint, payload=payload, headers=headers)

    def validate_access_token(self, token: str, *, client_id: str) -> dict[str, Any]:
        metadata = self.fetch_metadata()
        jwks = self._fetch_jwks(metadata.jwks_uri)
        header = jwt.get_unverified_header(token)
        matching_keys = [
            key for key in jwks.get("keys", []) if key.get("kid") == header.get("kid") and key.get("alg") == header.get("alg")
        ]
        if not matching_keys:
            raise JWTError("Unable to match JWT signing key.")

        claims = jwt.decode(
            token,
            key=matching_keys[0],
            algorithms=[header["alg"]],
            issuer=ACCEPTED_ISSUERS,
            audience="EVE Online",
        )
        audience = claims.get("aud", [])
        if isinstance(audience, str):
            audience_values = (audience,)
        else:
            audience_values = tuple(str(value) for value in audience)

        if client_id not in audience_values:
            raise JWTError("The token audience does not include the configured client id.")

        return claims

    def _fetch_jwks(self, jwks_uri: str) -> dict[str, Any]:
        cached = self._jwks_cache
        if cached is not None and cached[1] > _utc_now():
            return cached[0]

        payload = self._request_json("GET", jwks_uri)
        self._jwks_cache = (
            payload,
            _utc_now() + timedelta(seconds=self._metadata_cache_ttl_seconds),
        )
        return payload

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self._request_raw(method, url, payload=payload, headers=headers)
        return json.loads(response.decode("utf-8"))

    def _request_raw(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> bytes:
        request_headers = {"User-Agent": self._user_agent}
        if headers:
            request_headers.update(headers)

        body = None
        if payload is not None:
            body = urllib.parse.urlencode(payload).encode("utf-8")

        request = urllib.request.Request(url, method=method, headers=request_headers, data=body)
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            return response.read()

    @staticmethod
    def _apply_basic_auth(registration: EsiClientRegistration, headers: dict[str, str]) -> None:
        if registration.client_secret is None:
            raise RuntimeError("The configured ESI client registration does not include a client secret.")

        basic_auth = base64.b64encode(
            f"{registration.client_id}:{registration.client_secret}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {basic_auth}"

    def _form_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": self._user_agent,
        }
