from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.app.config import load_app_config
from eve_craft.platform.auth.domain.models import AuthenticatedCharacter
from eve_craft.platform.characters.settings_keys import DEFAULT_CHARACTER_SETTING_KEY
from eve_craft.platform.db.models import AppBase
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.domain.models import EsiOperationDescriptor
from eve_craft.platform.esi.domain.pagination import EsiAuthMode
from eve_craft.platform.esi.service import EsiService
from eve_craft.platform.settings.service import SettingsService


class FakeAuthService:
    def __init__(self, characters: tuple[AuthenticatedCharacter, ...]) -> None:
        self._characters = characters

    def list_authorized_characters(self) -> tuple[AuthenticatedCharacter, ...]:
        return self._characters

    def get_status(self):
        class Status:
            configured = True
            authorized_characters = len(self._characters)

        return Status()


class CapturingExecutor:
    def __init__(self) -> None:
        self.contexts = []

    def execute(self, context):
        self.contexts.append(context)

        class Envelope:
            payload = {"ok": True}
            requested_at = datetime.now(timezone.utc)
            status_code = 200
            etag = None
            expires_at = None
            last_modified = None
            rate_limits = None
            pagination = None
            source = "test"

        return Envelope()


def _build_authenticated_character(character_id: int, name: str) -> AuthenticatedCharacter:
    return AuthenticatedCharacter(
        character_id=character_id,
        character_name=name,
        subject=f"CHARACTER:EVE:{character_id}",
        owner_hash="owner-hash",
        scopes=("publicData", "esi-assets.read_assets.v1"),
        audience=("EVE Online", "client-id"),
        access_token=f"access-{character_id}",
        refresh_token=f"refresh-{character_id}",
        token_type="Bearer",
        expires_at=datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
    )


class EsiServiceDefaultCharacterTests(unittest.TestCase):
    def test_execute_uses_default_character_when_no_character_id_is_passed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = load_app_config()
            config = replace(
                config,
                paths=replace(
                    config.paths,
                    app_database_path=root / "app.sqlite3",
                    settings_path=root / "settings.json",
                ),
            )
            database = DatabaseManager(config.paths.app_database_path)
            AppBase.metadata.create_all(database.engine)
            settings = SettingsService(config.paths.settings_path)
            settings.set(DEFAULT_CHARACTER_SETTING_KEY, 90000002)
            auth = FakeAuthService(
                (
                    _build_authenticated_character(90000001, "Pilot One"),
                    _build_authenticated_character(90000002, "Pilot Two"),
                )
            )
            service = EsiService(config=config, database=database, auth=auth, settings=settings)
            executor = CapturingExecutor()
            service._executor = executor
            operation = EsiOperationDescriptor(
                key="character.assets",
                method="GET",
                path="/characters/{character_id}/assets/",
                auth_mode=EsiAuthMode.CHARACTER,
            )

            service.execute(operation)

            self.assertEqual(90000002, executor.contexts[0].character_id)
            self.assertEqual(90000002, executor.contexts[0].route_params["character_id"])
            database.dispose()

    def test_execute_falls_back_to_first_authorized_character_when_default_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = load_app_config()
            config = replace(
                config,
                paths=replace(
                    config.paths,
                    app_database_path=root / "app.sqlite3",
                    settings_path=root / "settings.json",
                ),
            )
            database = DatabaseManager(config.paths.app_database_path)
            AppBase.metadata.create_all(database.engine)
            settings = SettingsService(config.paths.settings_path)
            settings.set(DEFAULT_CHARACTER_SETTING_KEY, 99999999)
            auth = FakeAuthService((_build_authenticated_character(90000001, "Pilot One"),))
            service = EsiService(config=config, database=database, auth=auth, settings=settings)
            executor = CapturingExecutor()
            service._executor = executor
            operation = EsiOperationDescriptor(
                key="character.assets",
                method="GET",
                path="/characters/{character_id}/assets/",
                auth_mode=EsiAuthMode.CHARACTER,
            )

            service.execute(operation)

            self.assertEqual(90000001, executor.contexts[0].character_id)
            self.assertEqual(90000001, executor.contexts[0].route_params["character_id"])
            self.assertEqual(90000001, settings.get(DEFAULT_CHARACTER_SETTING_KEY))
            database.dispose()
