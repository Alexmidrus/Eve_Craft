from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.platform.auth.domain.models import AuthenticatedCharacter
from eve_craft.platform.characters.service import CharacterService
from eve_craft.platform.db.models import AppBase
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.settings.service import SettingsService


class FakeAuthService:
    def __init__(self, characters: tuple[AuthenticatedCharacter, ...]) -> None:
        self._characters = list(characters)
        self.refresh_requests: list[int] = []
        self.revoke_requests: list[int] = []

    def list_authorized_characters(self) -> tuple[AuthenticatedCharacter, ...]:
        return tuple(self._characters)

    def refresh_character(self, character_id: int) -> AuthenticatedCharacter:
        self.refresh_requests.append(character_id)
        character = next(character for character in self._characters if character.character_id == character_id)
        refreshed = AuthenticatedCharacter(
            character_id=character.character_id,
            character_name=character.character_name,
            subject=character.subject,
            owner_hash=character.owner_hash,
            scopes=character.scopes,
            audience=character.audience,
            access_token=f"{character.access_token}-refreshed",
            refresh_token=character.refresh_token,
            token_type=character.token_type,
            expires_at=character.expires_at,
        )
        self._characters = [
            refreshed if candidate.character_id == character_id else candidate for candidate in self._characters
        ]
        return refreshed

    def revoke_character(self, character_id: int) -> None:
        self.revoke_requests.append(character_id)
        self._characters = [character for character in self._characters if character.character_id != character_id]


class FakeEsiService:
    def __init__(self, payloads: dict[int, dict[str, object]]) -> None:
        self._payloads = dict(payloads)
        self.registered_operations: list[str] = []
        self.requests: list[tuple[int, bool]] = []

    def register_operation(self, operation):
        self.registered_operations.append(operation.key)
        return operation

    def execute(self, operation, *, route_params=None, force_refresh=False, **_kwargs):
        character_id = int((route_params or {})["character_id"])
        self.requests.append((character_id, force_refresh))

        class Envelope:
            def __init__(self, payload):
                self.payload = payload

        return Envelope(self._payloads[character_id])


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


class CharacterServiceTests(unittest.TestCase):
    def test_handle_authorized_character_syncs_public_profile_and_sets_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = DatabaseManager(root / "app.sqlite3")
            settings = SettingsService(root / "settings.json")
            auth = FakeAuthService((_build_authenticated_character(90000001, "Pilot One"),))
            esi = FakeEsiService(
                {
                    90000001: {
                        "name": "Pilot One",
                        "corporation_id": 123456,
                    }
                }
            )
            service = CharacterService(auth=auth, esi=esi, settings=settings, database=database)
            AppBase.metadata.create_all(database.engine)

            managed_character = service.handle_authorized_character(auth.list_authorized_characters()[0])

            self.assertEqual(90000001, service.get_default_character_id())
            self.assertEqual(123456, managed_character.corporation_id)
            self.assertTrue(managed_character.is_default)
            self.assertEqual([(90000001, True)], esi.requests)
            database.dispose()

    def test_revoke_character_moves_default_to_next_authorized_character(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            database = DatabaseManager(root / "app.sqlite3")
            settings = SettingsService(root / "settings.json")
            auth = FakeAuthService(
                (
                    _build_authenticated_character(90000001, "Pilot One"),
                    _build_authenticated_character(90000002, "Pilot Two"),
                )
            )
            esi = FakeEsiService(
                {
                    90000001: {"name": "Pilot One", "corporation_id": 123456},
                    90000002: {"name": "Pilot Two", "corporation_id": 654321},
                }
            )
            service = CharacterService(auth=auth, esi=esi, settings=settings, database=database)
            AppBase.metadata.create_all(database.engine)
            service.set_default_character(90000001)

            service.revoke_character(90000001)

            self.assertEqual([90000001], auth.revoke_requests)
            self.assertEqual(90000002, service.get_default_character_id())
            database.dispose()
