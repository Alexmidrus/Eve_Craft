from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

try:
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError:  # pragma: no cover - dependency gate
    QApplication = None

from eve_craft.app.config import load_app_config
from eve_craft.platform.auth.domain.models import AuthenticatedCharacter, EsiClientRegistration
from eve_craft.platform.characters.domain.models import ManagedCharacter
from eve_craft.platform.characters.presentation.windows import AddCharacterWindowController, ManageAccountsWindowController


class FakeAuthService:
    def __init__(self, characters: tuple[AuthenticatedCharacter, ...] = ()) -> None:
        self._characters = list(characters)
        self.authorization_requests: list[tuple[str, ...]] = []
        self.refresh_requests: list[int] = []
        self.revoked_characters: list[int] = []

    def registration(self) -> EsiClientRegistration:
        return EsiClientRegistration(
            client_id="client-id",
            callback_url="http://127.0.0.1:8080/callback",
            use_pkce=True,
        )

    def list_authorized_characters(self) -> tuple[AuthenticatedCharacter, ...]:
        return tuple(self._characters)

    def authorize_with_local_callback(self, scopes: list[str] | tuple[str, ...]) -> AuthenticatedCharacter:
        self.authorization_requests.append(tuple(scopes))
        character = AuthenticatedCharacter(
            character_id=90000001,
            character_name="Authorized Pilot",
            subject="CHARACTER:EVE:90000001",
            owner_hash="owner-hash",
            scopes=tuple(scopes),
            audience=("EVE Online", "client-id"),
            access_token="access-token",
            refresh_token="refresh-token",
            token_type="Bearer",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        self._characters = [character]
        return character

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
            access_token="refreshed-token",
            refresh_token=character.refresh_token,
            token_type=character.token_type,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        self._characters = [
            refreshed if candidate.character_id == character_id else candidate for candidate in self._characters
        ]
        return refreshed

    def revoke_character(self, character_id: int) -> None:
        self.revoked_characters.append(character_id)
        self._characters = [character for character in self._characters if character.character_id != character_id]


class FakeCharacterService:
    def __init__(self, auth_service: FakeAuthService) -> None:
        self._auth_service = auth_service
        self._corporation_ids: dict[int, int] = {}
        self._default_character_id: int | None = None
        self.handled_authorizations: list[int] = []
        self.default_requests: list[int] = []

    def list_managed_characters(self) -> tuple[ManagedCharacter, ...]:
        authorized_characters = self._auth_service.list_authorized_characters()
        self._normalize_default_character(authorized_characters)
        return tuple(self._build_managed_character(character) for character in authorized_characters)

    def get_managed_character(self, character_id: int, *, sync_if_missing: bool = False) -> ManagedCharacter | None:
        character = next(
            (candidate for candidate in self._auth_service.list_authorized_characters() if candidate.character_id == character_id),
            None,
        )
        if character is None:
            return None

        if sync_if_missing and character_id not in self._corporation_ids:
            self._corporation_ids[character_id] = 98000000 + len(self._corporation_ids) + 1

        return self._build_managed_character(character)

    def handle_authorized_character(self, character: AuthenticatedCharacter) -> ManagedCharacter:
        self.handled_authorizations.append(character.character_id)
        self._corporation_ids[character.character_id] = 98000000 + character.character_id % 100
        if self._default_character_id is None:
            self._default_character_id = character.character_id
        return self._build_managed_character(character)

    def refresh_character_data(self, character_id: int) -> ManagedCharacter:
        refreshed = self._auth_service.refresh_character(character_id)
        self._corporation_ids[character_id] = 99000000 + character_id % 100
        self._normalize_default_character(self._auth_service.list_authorized_characters())
        return self._build_managed_character(refreshed)

    def revoke_character(self, character_id: int) -> None:
        self._auth_service.revoke_character(character_id)
        self._corporation_ids.pop(character_id, None)
        self._normalize_default_character(self._auth_service.list_authorized_characters())

    def set_default_character(self, character_id: int) -> ManagedCharacter:
        self.default_requests.append(character_id)
        self._default_character_id = character_id
        managed_character = self.get_managed_character(character_id)
        if managed_character is None:
            raise RuntimeError("Character is not authorized.")
        return ManagedCharacter(
            authorization=managed_character.authorization,
            corporation_id=managed_character.corporation_id,
            alliance_id=managed_character.alliance_id,
            is_default=True,
        )

    def get_default_character_id(self) -> int | None:
        self._normalize_default_character(self._auth_service.list_authorized_characters())
        return self._default_character_id

    def _normalize_default_character(self, characters: tuple[AuthenticatedCharacter, ...]) -> None:
        if not characters:
            self._default_character_id = None
            return

        character_ids = {character.character_id for character in characters}
        if self._default_character_id in character_ids:
            return

        self._default_character_id = characters[0].character_id

    def _build_managed_character(self, character: AuthenticatedCharacter) -> ManagedCharacter:
        return ManagedCharacter(
            authorization=character,
            corporation_id=self._corporation_ids.get(character.character_id),
            is_default=character.character_id == self._default_character_id,
        )


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class CharacterManagementWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._application = QApplication.instance() or QApplication([])

    def test_manage_accounts_window_stays_top_level_when_parented(self) -> None:
        config = load_app_config()
        parent = QWidget()
        auth_service = FakeAuthService()
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=FakeCharacterService(auth_service),
            parent=parent,
        )

        self.assertTrue(controller.window.isWindow())
        self.assertEqual(parent, controller.window.parentWidget())

        controller.window.close()
        parent.close()

    def test_add_character_button_opens_the_add_character_window(self) -> None:
        config = load_app_config()
        auth_service = FakeAuthService()
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=FakeCharacterService(auth_service),
        )

        controller._add_character_button.click()

        self.assertIsNotNone(controller._add_character_window)
        self.assertTrue(controller._add_character_window.window.isWindow())
        self.assertEqual(controller.window, controller._add_character_window.window.parentWidget())

        controller._add_character_window.close()
        controller.window.close()

    def test_manage_accounts_renders_authorized_character_details(self) -> None:
        config = load_app_config()
        auth_service = FakeAuthService(
            characters=(
                AuthenticatedCharacter(
                    character_id=90000001,
                    character_name="Test Pilot",
                    subject="CHARACTER:EVE:90000001",
                    owner_hash="owner-hash",
                    scopes=("publicData", "esi-assets.read_assets.v1"),
                    audience=("EVE Online", "client-id"),
                    access_token="access-token",
                    refresh_token="refresh-token",
                    token_type="Bearer",
                    expires_at=datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
                ),
            )
        )
        character_service = FakeCharacterService(auth_service)
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=character_service,
        )

        self.assertEqual("90000001", controller._character_id_field.text())
        self.assertEqual("access-token", controller._access_token_field.text())
        self.assertEqual("98000001", controller._corporation_id_field.text())
        self.assertEqual(2, controller._scopes_tree.topLevelItemCount())
        self.assertIn("[Default]", controller._accounts_tree.topLevelItem(0).text(0))

        controller.window.close()

    def test_add_character_login_calls_auth_service_and_refreshes_account_list(self) -> None:
        config = load_app_config()
        auth_service = FakeAuthService()
        character_service = FakeCharacterService(auth_service)
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=character_service,
        )
        controller._open_add_character_window()
        assert controller._add_character_window is not None
        add_window = controller._add_character_window
        add_window._find_checkbox("chkReadCharacterAssets").setChecked(True)

        with patch("eve_craft.platform.characters.presentation.windows.QMessageBox.information", return_value=None):
            with patch("eve_craft.platform.characters.presentation.windows.QMessageBox.warning", return_value=None):
                add_window._login_button.click()

                deadline = time.monotonic() + 3
                while time.monotonic() < deadline and add_window.is_busy:
                    self._application.processEvents()
                    time.sleep(0.01)

        self.assertIn(("publicData", "esi-assets.read_assets.v1"), auth_service.authorization_requests)
        self.assertEqual([90000001], character_service.handled_authorizations)
        self.assertEqual(1, controller._accounts_tree.topLevelItemCount())
        self.assertEqual("90000001", controller._character_id_field.text())
        self.assertEqual("98000001", controller._corporation_id_field.text())

        controller.window.close()

    def test_refresh_token_button_updates_token_fields(self) -> None:
        config = load_app_config()
        auth_service = FakeAuthService(
            characters=(
                AuthenticatedCharacter(
                    character_id=90000001,
                    character_name="Refresh Pilot",
                    subject="CHARACTER:EVE:90000001",
                    owner_hash="owner-hash",
                    scopes=("publicData",),
                    audience=("EVE Online", "client-id"),
                    access_token="access-token",
                    refresh_token="refresh-token",
                    token_type="Bearer",
                    expires_at=datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
                ),
            )
        )
        character_service = FakeCharacterService(auth_service)
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=character_service,
        )

        controller._refresh_token_button.click()

        self.assertEqual([90000001], auth_service.refresh_requests)
        self.assertEqual("refreshed-token", controller._access_token_field.text())
        self.assertEqual("99000001", controller._corporation_id_field.text())

        controller.window.close()

    def test_set_default_character_marks_selected_character(self) -> None:
        config = load_app_config()
        auth_service = FakeAuthService(
            characters=(
                AuthenticatedCharacter(
                    character_id=90000001,
                    character_name="First Pilot",
                    subject="CHARACTER:EVE:90000001",
                    owner_hash="owner-hash",
                    scopes=("publicData",),
                    audience=("EVE Online", "client-id"),
                    access_token="token-1",
                    refresh_token="refresh-1",
                    token_type="Bearer",
                    expires_at=datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
                ),
                AuthenticatedCharacter(
                    character_id=90000002,
                    character_name="Second Pilot",
                    subject="CHARACTER:EVE:90000002",
                    owner_hash="owner-hash",
                    scopes=("publicData",),
                    audience=("EVE Online", "client-id"),
                    access_token="token-2",
                    refresh_token="refresh-2",
                    token_type="Bearer",
                    expires_at=datetime(2026, 4, 11, 18, 0, tzinfo=timezone.utc),
                ),
            )
        )
        character_service = FakeCharacterService(auth_service)
        controller = ManageAccountsWindowController(
            config=config,
            auth_service=auth_service,
            character_service=character_service,
        )

        controller._accounts_tree.setCurrentItem(controller._accounts_tree.topLevelItem(1))
        controller._default_character_button.click()

        self.assertEqual([90000002], character_service.default_requests)
        self.assertEqual(90000002, controller._selected_character_id())
        self.assertIn("[Default]", controller._accounts_tree.topLevelItem(1).text(0))
        self.assertNotIn("[Default]", controller._accounts_tree.topLevelItem(0).text(0))

        controller.window.close()

    def test_select_all_and_deselect_all_toggle_scope_checkboxes(self) -> None:
        config = load_app_config()
        controller = AddCharacterWindowController(config=config, auth_service=FakeAuthService())

        controller._select_all_button.click()
        self.assertTrue(controller._find_checkbox("chkReadCharacterAssets").isChecked())
        self.assertTrue(controller._find_checkbox("chkReadCorporationAssets").isChecked())
        self.assertFalse(controller._find_checkbox("chkReadCharacterShipLocation").isEnabled())

        controller._deselect_all_button.click()
        self.assertFalse(controller._find_checkbox("chkReadCharacterAssets").isChecked())
        self.assertFalse(controller._find_checkbox("chkReadCorporationAssets").isChecked())

        controller.window.close()
