from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from eve_craft.app.config import AppConfig, AppPaths, EsiConfig
from eve_craft.platform.auth.domain.models import AuthenticatedCharacter, SsoMetadata
from eve_craft.platform.auth.infrastructure.sso_client import TokenExchangePayload
from eve_craft.platform.auth.service import AuthService
from eve_craft.platform.db.models import AppBase
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.settings.service import SettingsService


def _build_test_config(root: Path) -> AppConfig:
    placeholder = root / "placeholder"
    paths = AppPaths(
        project_root=root,
        src_root=root,
        package_root=root,
        runtime_dir=root,
        resources_dir=root,
        sde_resources_dir=root,
        databases_dir=root,
        downloads_dir=root,
        temporary_dir=root,
        ui_design_dir=root,
        main_window_ui=placeholder,
        startup_splash_ui=placeholder,
        sde_update_dialog_ui=placeholder,
        manage_accounts_ui=placeholder,
        add_character_ui=placeholder,
        icon_file=placeholder,
        logs_dir=root,
        app_database_path=root / "app.sqlite3",
        sde_database_path=root / "sde.sqlite3",
        types_images_dir=root / "types",
        settings_path=root / "settings.json",
    )
    return AppConfig(
        application_name="Eve Craft",
        organization_name="Eve Craft",
        paths=paths,
        esi=EsiConfig(
            base_url="https://esi.evetech.net/latest",
            sso_metadata_url="https://login.eveonline.com/.well-known/oauth-authorization-server",
            default_callback_url="http://127.0.0.1:8080/callback",
            compatibility_date="2026-04-11",
            user_agent="EveCraft/test",
            request_timeout_seconds=30,
            metadata_cache_ttl_seconds=300,
            token_refresh_skew_seconds=60,
            x_pages_expiry_safety_window_seconds=5,
        ),
    )


class FakeSsoClient:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.revoked_tokens: list[str] = []

    def fetch_metadata(self) -> SsoMetadata:
        return SsoMetadata(
            issuer="https://login.eveonline.com/",
            authorization_endpoint="https://login.eveonline.com/v2/oauth/authorize",
            token_endpoint="https://login.eveonline.com/v2/oauth/token",
            jwks_uri="https://login.eveonline.com/oauth/jwks",
            revocation_endpoint="https://login.eveonline.com/v2/oauth/revoke",
        )

    def generate_pkce_pair(self) -> tuple[str, str]:
        return "verifier-123", "challenge-456"

    def exchange_code(self, registration, authorization_code: str, code_verifier: str | None) -> TokenExchangePayload:
        assert registration.client_id == "client-id"
        assert authorization_code == "auth-code"
        assert code_verifier == "verifier-123"
        return TokenExchangePayload(
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_in=3600,
        )

    def refresh_token(self, registration, refresh_token: str) -> TokenExchangePayload:
        self.refresh_calls += 1
        assert refresh_token == "refresh-token"
        return TokenExchangePayload(
            access_token="refreshed-access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_in=7200,
        )

    def revoke_token(self, registration, token: str) -> None:
        self.revoked_tokens.append(token)

    def validate_access_token(self, token: str, *, client_id: str):
        assert client_id == "client-id"
        if token == "refreshed-access-token":
            expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        else:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        _ = expires_at
        return {
            "sub": "CHARACTER:EVE:90000001",
            "name": "Test Pilot",
            "owner": "owner-hash",
            "scp": ["esi-assets.read_assets.v1"],
            "aud": ["EVE Online", "client-id"],
        }


class AuthServiceTests(unittest.TestCase):
    def test_begin_authorization_builds_pkce_url_and_completes_code_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_test_config(root)
            settings = SettingsService(config.paths.settings_path)
            database = DatabaseManager(config.paths.app_database_path)
            AppBase.metadata.create_all(database.engine)
            service = AuthService(config=config, settings=settings, database=database)
            service._sso_client = FakeSsoClient()
            service.configure_client(client_id="client-id", callback_url=config.esi.default_callback_url)

            session = service.begin_authorization(["esi-assets.read_assets.v1"])
            parsed = urlparse(session.authorize_url)
            query = parse_qs(parsed.query)

            self.assertEqual("https", parsed.scheme)
            self.assertEqual(["client-id"], query["client_id"])
            self.assertEqual(["code"], query["response_type"])
            self.assertEqual(["verifier-123"], [session.code_verifier])
            self.assertEqual(["challenge-456"], query["code_challenge"])
            self.assertEqual(["S256"], query["code_challenge_method"])

            callback_url = f"{config.esi.default_callback_url}?code=auth-code&state={session.state}"
            character = service.complete_authorization_callback(callback_url)

            self.assertEqual(90000001, character.character_id)
            self.assertEqual("Test Pilot", character.character_name)
            self.assertEqual("access-token", service.get_valid_access_token(90000001))
            self.assertEqual(1, len(service.list_authorized_characters()))

            database.dispose()

    def test_authorize_with_local_callback_uses_browser_and_listener(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_test_config(root)
            settings = SettingsService(config.paths.settings_path)
            database = DatabaseManager(config.paths.app_database_path)
            AppBase.metadata.create_all(database.engine)
            service = AuthService(config=config, settings=settings, database=database)
            service._sso_client = FakeSsoClient()
            service.configure_client(client_id="client-id", callback_url=config.esi.default_callback_url)

            browser_calls: list[str] = []
            state_holder: dict[str, str] = {}

            def browser_opener(url: str) -> bool:
                browser_calls.append(url)
                state_holder["state"] = parse_qs(urlparse(url).query)["state"][0]
                return True

            class FakeListener:
                def __init__(self, callback_url: str) -> None:
                    self.callback_url = callback_url

                def wait_for_callback(self, timeout_seconds: int = 180) -> str:
                    return f"{self.callback_url}?code=auth-code&state={state_holder['state']}"

            character = service.authorize_with_local_callback(
                ["esi-assets.read_assets.v1"],
                callback_listener_factory=FakeListener,
                browser_opener=browser_opener,
            )

            self.assertEqual("Test Pilot", character.character_name)
            self.assertEqual(1, len(browser_calls))
            self.assertEqual(1, len(service.list_authorized_characters()))

            database.dispose()

    def test_get_valid_access_token_refreshes_expired_token(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = _build_test_config(root)
            settings = SettingsService(config.paths.settings_path)
            database = DatabaseManager(config.paths.app_database_path)
            AppBase.metadata.create_all(database.engine)
            service = AuthService(config=config, settings=settings, database=database)
            fake_sso = FakeSsoClient()
            service._sso_client = fake_sso
            service.configure_client(client_id="client-id", callback_url=config.esi.default_callback_url)

            expired_character = AuthenticatedCharacter(
                character_id=90000001,
                character_name="Test Pilot",
                subject="CHARACTER:EVE:90000001",
                owner_hash="owner-hash",
                scopes=("esi-assets.read_assets.v1",),
                audience=("EVE Online", "client-id"),
                access_token="stale-token",
                refresh_token="refresh-token",
                token_type="Bearer",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            service._token_repository.save(expired_character)

            access_token = service.get_valid_access_token(
                90000001,
                required_scopes=("esi-assets.read_assets.v1",),
            )

            self.assertEqual("refreshed-access-token", access_token)
            self.assertEqual(1, fake_sso.refresh_calls)

            database.dispose()
