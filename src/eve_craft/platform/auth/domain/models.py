from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class EsiClientRegistration:
    client_id: str
    callback_url: str
    client_secret: str | None = None
    use_pkce: bool = True


@dataclass(frozen=True, slots=True)
class SsoMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    revocation_endpoint: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationSession:
    authorize_url: str
    state: str
    scopes: tuple[str, ...]
    callback_url: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    code_verifier: str | None = None


@dataclass(frozen=True, slots=True)
class CallbackPayload:
    state: str
    code: str | None = None
    error: str | None = None
    error_description: str | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedCharacter:
    character_id: int
    character_name: str
    subject: str
    owner_hash: str | None
    scopes: tuple[str, ...]
    audience: tuple[str, ...]
    access_token: str
    refresh_token: str | None
    token_type: str
    expires_at: datetime
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def expires_in_seconds(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        return int((self.expires_at - now).total_seconds())

    def is_expired(self, now: datetime | None = None, *, skew_seconds: int = 0) -> bool:
        return self.expires_in_seconds(now) <= skew_seconds

