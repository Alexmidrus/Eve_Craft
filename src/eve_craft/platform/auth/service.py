from __future__ import annotations

import os
import secrets
import urllib.parse
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from jose.exceptions import JWTError

from eve_craft.app.config import AppConfig
from eve_craft.platform.auth.domain.models import (
    AuthenticatedCharacter,
    AuthorizationSession,
    CallbackPayload,
    EsiClientRegistration,
)
from eve_craft.platform.auth.infrastructure.repository import AuthTokenRepository
from eve_craft.platform.auth.infrastructure.callback_listener import LocalOAuthCallbackListener
from eve_craft.platform.auth.infrastructure.sso_client import EveSsoClient
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.settings.service import SettingsService


@dataclass(frozen=True, slots=True)
class AuthStatus:
    configured: bool
    authorized_characters: int
    callback_url: str | None


class AuthService:
    SETTINGS_KEY = "esi_auth"

    def __init__(self, config: AppConfig, settings: SettingsService, database: DatabaseManager) -> None:
        self._config = config
        self._settings = settings
        self._token_repository = AuthTokenRepository(database)
        self._sso_client = EveSsoClient(
            metadata_url=config.esi.sso_metadata_url,
            user_agent=config.esi.user_agent,
            timeout_seconds=config.esi.request_timeout_seconds,
            metadata_cache_ttl_seconds=config.esi.metadata_cache_ttl_seconds,
        )
        self._pending_sessions: dict[str, AuthorizationSession] = {}

    def configure_client(
        self,
        *,
        client_id: str,
        client_secret: str | None = None,
        callback_url: str | None = None,
        use_pkce: bool = True,
    ) -> None:
        self._settings.set(
            self.SETTINGS_KEY,
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "callback_url": callback_url or self._config.esi.default_callback_url,
                "use_pkce": use_pkce,
            },
        )

    def registration(self) -> EsiClientRegistration | None:
        settings_payload = self._settings.get(self.SETTINGS_KEY, {}) or {}
        client_id = os.environ.get("EVE_CRAFT_ESI_CLIENT_ID") or settings_payload.get("client_id")
        if not client_id:
            return None

        client_secret = os.environ.get("EVE_CRAFT_ESI_CLIENT_SECRET") or settings_payload.get("client_secret")
        callback_url = (
            os.environ.get("EVE_CRAFT_ESI_CALLBACK_URL")
            or settings_payload.get("callback_url")
            or self._config.esi.default_callback_url
        )
        use_pkce = settings_payload.get("use_pkce", True)

        return EsiClientRegistration(
            client_id=str(client_id),
            client_secret=str(client_secret) if client_secret else None,
            callback_url=str(callback_url),
            use_pkce=bool(use_pkce),
        )

    def begin_authorization(self, scopes: list[str] | tuple[str, ...]) -> AuthorizationSession:
        registration = self._require_registration()
        metadata = self._sso_client.fetch_metadata()
        requested_scopes = tuple(dict.fromkeys(str(scope) for scope in scopes))
        state = secrets.token_urlsafe(16)

        query_params: dict[str, str] = {
            "response_type": "code",
            "client_id": registration.client_id,
            "redirect_uri": registration.callback_url,
            "scope": " ".join(requested_scopes),
            "state": state,
        }
        code_verifier = None
        if registration.use_pkce or not registration.client_secret:
            code_verifier, code_challenge = self._sso_client.generate_pkce_pair()
            query_params["code_challenge"] = code_challenge
            query_params["code_challenge_method"] = "S256"

        authorize_url = f"{metadata.authorization_endpoint}?{urllib.parse.urlencode(query_params)}"
        session = AuthorizationSession(
            authorize_url=authorize_url,
            state=state,
            scopes=requested_scopes,
            callback_url=registration.callback_url,
            code_verifier=code_verifier,
        )
        self._pending_sessions[state] = session
        return session

    def complete_authorization_callback(self, callback_url: str) -> AuthenticatedCharacter:
        callback = self.parse_callback_url(callback_url)
        if callback.error:
            if callback.state:
                self._pending_sessions.pop(callback.state, None)
            message = callback.error_description or callback.error
            raise RuntimeError(f"SSO authorization failed: {message}")

        if callback.code is None:
            if callback.state:
                self._pending_sessions.pop(callback.state, None)
            raise RuntimeError("The callback URL does not contain an authorization code.")

        return self.complete_authorization_code(state=callback.state, authorization_code=callback.code)

    def authorize_with_local_callback(
        self,
        scopes: list[str] | tuple[str, ...],
        *,
        timeout_seconds: int = 180,
        callback_listener_factory: Callable[[str], object] | None = None,
        browser_opener: Callable[[str], object] | None = None,
    ) -> AuthenticatedCharacter:
        session = self.begin_authorization(scopes)
        listener_factory = callback_listener_factory or LocalOAuthCallbackListener
        listener = listener_factory(session.callback_url)
        opener = browser_opener or webbrowser.open

        try:
            open_result = opener(session.authorize_url)
            if open_result is False:
                raise RuntimeError("Unable to open the system browser for EVE SSO authorization.")

            callback_url = listener.wait_for_callback(timeout_seconds=timeout_seconds)
            return self.complete_authorization_callback(callback_url)
        except Exception:
            self._pending_sessions.pop(session.state, None)
            raise

    def complete_authorization_code(self, *, state: str, authorization_code: str) -> AuthenticatedCharacter:
        registration = self._require_registration()
        session = self._pending_sessions.pop(state, None)
        if session is None:
            raise RuntimeError("Unknown or expired SSO authorization state.")

        payload = self._sso_client.exchange_code(
            registration=registration,
            authorization_code=authorization_code,
            code_verifier=session.code_verifier,
        )
        token = self._build_authenticated_character(
            registration=registration,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            token_type=payload.token_type,
            expires_in=payload.expires_in,
        )
        self._token_repository.save(token)
        return token

    def list_authorized_characters(self) -> tuple[AuthenticatedCharacter, ...]:
        return self._token_repository.list_all()

    def get_valid_access_token(
        self,
        character_id: int,
        *,
        required_scopes: tuple[str, ...] | list[str] = (),
    ) -> str:
        token = self._token_repository.get(character_id)
        if token is None:
            raise RuntimeError(f"Character {character_id} is not authorized in the local token store.")

        if token.is_expired(skew_seconds=self._config.esi.token_refresh_skew_seconds):
            token = self.refresh_character(character_id)

        missing_scopes = [scope for scope in required_scopes if scope not in token.scopes]
        if missing_scopes:
            raise RuntimeError(
                f"Character {character_id} token does not include required scopes: {', '.join(missing_scopes)}"
            )

        return token.access_token

    def refresh_character(self, character_id: int) -> AuthenticatedCharacter:
        token = self._token_repository.get(character_id)
        if token is None:
            raise RuntimeError(f"Character {character_id} is not authorized in the local token store.")
        if token.refresh_token is None:
            raise RuntimeError(f"Character {character_id} token does not include a refresh token.")

        registration = self._require_registration()
        payload = self._sso_client.refresh_token(registration=registration, refresh_token=token.refresh_token)
        refreshed = self._build_authenticated_character(
            registration=registration,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            token_type=payload.token_type,
            expires_in=payload.expires_in,
        )
        self._token_repository.save(refreshed)
        return refreshed

    def revoke_character(self, character_id: int) -> None:
        token = self._token_repository.get(character_id)
        if token is None:
            return

        registration = self.registration()
        if registration is not None and token.refresh_token:
            self._sso_client.revoke_token(registration, token.refresh_token)

        self._token_repository.delete(character_id)

    def parse_callback_url(self, callback_url: str) -> CallbackPayload:
        parsed = urllib.parse.urlparse(callback_url)
        query = urllib.parse.parse_qs(parsed.query)
        return CallbackPayload(
            state=str(query.get("state", [""])[0]),
            code=self._first(query, "code"),
            error=self._first(query, "error"),
            error_description=self._first(query, "error_description"),
        )

    def get_status(self) -> AuthStatus:
        registration = self.registration()
        return AuthStatus(
            configured=registration is not None,
            authorized_characters=self._token_repository.count(),
            callback_url=registration.callback_url if registration is not None else None,
        )

    def describe_status(self) -> str:
        status = self.get_status()
        if not status.configured:
            return (
                "ESI SSO is not configured yet. Set ESI client registration via "
                "environment variables or runtime settings before authorizing characters."
            )

        return (
            "ESI SSO is configured. "
            f"Authorized characters: {status.authorized_characters}. "
            f"Callback URL: {status.callback_url}."
        )

    def _build_authenticated_character(
        self,
        *,
        registration: EsiClientRegistration,
        access_token: str,
        refresh_token: str | None,
        token_type: str,
        expires_in: int,
    ) -> AuthenticatedCharacter:
        try:
            claims = self._sso_client.validate_access_token(access_token, client_id=registration.client_id)
        except JWTError as error:
            raise RuntimeError("EVE SSO returned an access token that failed validation.") from error

        subject = str(claims["sub"])
        scopes_claim = claims.get("scp", [])
        if isinstance(scopes_claim, str):
            scopes = tuple(scope for scope in scopes_claim.split(" ") if scope)
        else:
            scopes = tuple(str(scope) for scope in scopes_claim)

        audience_claim = claims.get("aud", [])
        if isinstance(audience_claim, str):
            audience = (audience_claim,)
        else:
            audience = tuple(str(value) for value in audience_claim)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        character_id = self._parse_character_id(subject)

        return AuthenticatedCharacter(
            character_id=character_id,
            character_name=str(claims["name"]),
            subject=subject,
            owner_hash=claims.get("owner"),
            scopes=scopes,
            audience=audience,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_at=expires_at,
        )

    def _require_registration(self) -> EsiClientRegistration:
        registration = self.registration()
        if registration is None:
            raise RuntimeError(
                "ESI client registration is missing. Configure client_id/client_secret/callback_url first."
            )

        return registration

    @staticmethod
    def _parse_character_id(subject: str) -> int:
        prefix = "CHARACTER:EVE:"
        if not subject.startswith(prefix):
            raise RuntimeError(f"Unexpected EVE SSO subject format: {subject}")

        return int(subject.removeprefix(prefix))

    @staticmethod
    def _first(payload: dict[str, list[str]], key: str) -> str | None:
        values = payload.get(key)
        if not values:
            return None

        return str(values[0])
