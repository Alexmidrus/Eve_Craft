"""Presentation controllers for character management windows."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timezone

from PySide6.QtCore import QObject, QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from eve_craft.app.config import AppConfig
from eve_craft.app.presentation.background_tasks import BackgroundTaskWorker
from eve_craft.app.presentation.ui_loader import load_ui_widget
from eve_craft.platform.auth.domain.models import AuthenticatedCharacter
from eve_craft.platform.auth.service import AuthService
from eve_craft.platform.characters.domain.models import ManagedCharacter
from eve_craft.platform.characters.service import CharacterService


CHARACTER_SCOPE_CHECKBOXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("chkReadCharacterStandings", ("esi-characters.read_standings.v1",)),
    ("chkReadCharacterBlueprints", ("esi-characters.read_blueprints.v1",)),
    ("chkReadCharacterAgentsResearch", ("esi-characters.read_agents_research.v1",)),
    ("chkReadCharacterJobs", ("esi-industry.read_character_jobs.v1",)),
    ("chkReadCharacterAssets", ("esi-assets.read_assets.v1",)),
    ("chkReadCorporationMembership", ("esi-corporations.read_corporation_membership.v1", "esi-characters.read_corporation_roles.v1")),
    ("chkReadCorporationBlueprints", ("esi-corporations.read_blueprints.v1",)),
    ("chkReadCorporationDivisions", ("esi-corporations.read_divisions.v1",)),
    ("chkReadCorporationJobs", ("esi-industry.read_corporation_jobs.v1",)),
    ("chkReadCorporationAssets", ("esi-assets.read_corporation_assets.v1",)),
    (
        "chkReadStructures",
        (
            "esi-universe.read_structures.v1",
            "esi-corporations.read_structures.v1",
            "esi-structures.read_character.v1",
            "esi-structures.read_corporation.v1",
        ),
    ),
    ("chkReadStructureMarkets", ("esi-markets.structure_markets.v1",)),
)

UNSUPPORTED_SCOPE_CHECKBOXES: tuple[str, ...] = ("chkReadCharacterShipLocation",)


def _prepare_window(window: QWidget, *, config: AppConfig, parent: QWidget | None) -> None:
    if parent is not None:
        window.setParent(parent, window.windowFlags() | Qt.WindowType.Window)

    if config.paths.icon_file.exists():
        window.setWindowIcon(QIcon(str(config.paths.icon_file)))


def _show_window(window: QWidget) -> None:
    window.show()
    window.raise_()
    window.activateWindow()


class AddCharacterWindowController(QObject):
    def __init__(
        self,
        config: AppConfig,
        auth_service: AuthService,
        on_authorized: Callable[[AuthenticatedCharacter], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_service = auth_service
        self._on_authorized = on_authorized
        self.window = load_ui_widget(config.paths.add_character_ui)
        _prepare_window(self.window, config=config, parent=parent)

        self._select_all_button = self._find_button("btnSelectAll")
        self._deselect_all_button = self._find_button("btnDeselectAll")
        self._login_button = self._find_button("btnEVESSOLogin")
        self._scope_checkboxes: dict[QCheckBox, tuple[str, ...]] = {
            self._find_checkbox(object_name): scopes for object_name, scopes in CHARACTER_SCOPE_CHECKBOXES
        }
        self._unsupported_checkboxes = tuple(self._find_checkbox(object_name) for object_name in UNSUPPORTED_SCOPE_CHECKBOXES)
        self._thread: QThread | None = None
        self._worker: BackgroundTaskWorker[object] | None = None
        self._busy = False
        self._idle_title = self.window.windowTitle()

        self._select_all_button.clicked.connect(self._select_all_scopes)
        self._deselect_all_button.clicked.connect(self._deselect_all_scopes)
        self._login_button.clicked.connect(self._start_authorization)
        self.window.closeEvent = self._close_event

        for checkbox in self._unsupported_checkboxes:
            checkbox.setChecked(False)
            checkbox.setEnabled(False)
            checkbox.setToolTip("This permission is not part of the current ESI integration plan.")

    @property
    def is_busy(self) -> bool:
        return self._busy

    def show(self) -> None:
        _show_window(self.window)

    def close(self) -> None:
        self.window.close()

    def _select_all_scopes(self) -> None:
        for checkbox in self._scope_checkboxes:
            if checkbox.isEnabled() and not checkbox.isHidden():
                checkbox.setChecked(True)

    def _deselect_all_scopes(self) -> None:
        for checkbox in self._scope_checkboxes:
            checkbox.setChecked(False)

    def _selected_scopes(self) -> tuple[str, ...]:
        scopes = ["publicData"]
        for checkbox, checkbox_scopes in self._scope_checkboxes.items():
            if checkbox.isChecked():
                scopes.extend(checkbox_scopes)
        return tuple(dict.fromkeys(scopes))

    def _start_authorization(self) -> None:
        if self._busy:
            return

        if self._auth_service.registration() is None:
            QMessageBox.warning(
                self.window,
                "ESI SSO",
                (
                    "ESI SSO is not configured yet.\n\n"
                    "Set client credentials via environment variables or runtime settings:\n"
                    "EVE_CRAFT_ESI_CLIENT_ID\n"
                    "EVE_CRAFT_ESI_CLIENT_SECRET\n"
                    f"EVE_CRAFT_ESI_CALLBACK_URL={self._config.esi.default_callback_url}"
                ),
            )
            return

        scopes = self._selected_scopes()
        if scopes == ("publicData",):
            QMessageBox.information(
                self.window,
                "Select Permissions",
                "Choose at least one character or corporation permission before starting EVE SSO login.",
            )
            return

        self._busy = True
        self._set_controls_enabled(False)
        self.window.setWindowTitle("Add Character - Waiting for EVE SSO callback...")
        started = self._start_worker_task(
            task=lambda _report: self._auth_service.authorize_with_local_callback(scopes),
            success_handler=self._handle_authorization_success,
            failure_handler=self._handle_authorization_failure,
            finished_handler=self._authorization_finished,
        )
        if not started:
            self._busy = False
            self.window.setWindowTitle(self._idle_title)
            self._set_controls_enabled(True)

    @Slot(object)
    def _handle_authorization_success(self, character: AuthenticatedCharacter) -> None:
        self._busy = False
        if self._on_authorized is not None:
            self._on_authorized(character)

        QMessageBox.information(
            self.window,
            "Character Authorized",
            f"Character '{character.character_name}' was authorized successfully.",
        )
        self.window.close()

    @Slot(str)
    def _handle_authorization_failure(self, message: str) -> None:
        QMessageBox.warning(self.window, "ESI SSO", message)

    @Slot()
    def _authorization_finished(self) -> None:
        self._busy = False
        self.window.setWindowTitle(self._idle_title)
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._select_all_button.setEnabled(enabled)
        self._deselect_all_button.setEnabled(enabled)
        self._login_button.setEnabled(enabled)
        for checkbox in self._scope_checkboxes:
            checkbox.setEnabled(enabled)
        for checkbox in self._unsupported_checkboxes:
            checkbox.setEnabled(False)

    def _start_worker_task(
        self,
        *,
        task,
        success_handler,
        failure_handler,
        finished_handler,
    ) -> bool:
        if self._thread is not None or self._worker is not None:
            return False

        self._thread = QThread()
        self._worker = BackgroundTaskWorker(task)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.succeeded.connect(success_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(failure_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(finished_handler)
        self._thread.finished.connect(self._clear_worker_state)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        return True

    @Slot()
    def _clear_worker_state(self) -> None:
        self._thread = None
        self._worker = None

    def _close_event(self, event: QCloseEvent) -> None:
        if self._busy:
            event.ignore()
            return

        event.accept()

    def _find_button(self, object_name: str) -> QPushButton:
        button = self.window.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in character authorization UI.")

        return button

    def _find_checkbox(self, object_name: str) -> QCheckBox:
        checkbox = self.window.findChild(QCheckBox, object_name)
        if checkbox is None:
            raise LookupError(f"QCheckBox '{object_name}' was not found in character authorization UI.")

        return checkbox


class ManageAccountsWindowController(QObject):
    def __init__(
        self,
        config: AppConfig,
        auth_service: AuthService,
        character_service: CharacterService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._auth_service = auth_service
        self._character_service = character_service
        self.window = load_ui_widget(config.paths.manage_accounts_ui)
        _prepare_window(self.window, config=config, parent=parent)

        self._accounts_tree = self._find_tree_widget("lstAccounts")
        self._scopes_tree = self._find_tree_widget("lstScopes")
        self._add_character_window: AddCharacterWindowController | None = None
        self._managed_characters: dict[int, ManagedCharacter] = {}

        self._access_token_field = self._find_line_edit("txtAccessToken")
        self._character_id_field = self._find_line_edit("txtCharacterID")
        self._corporation_id_field = self._find_line_edit("txtCorpID")
        self._refresh_token_field = self._find_line_edit("txtRefreshToken")
        self._access_token_expiry_field = self._find_line_edit("txtAccessTokenExpDate")

        self._director_checkbox = self._find_checkbox("chkDirector")
        self._factory_manager_checkbox = self._find_checkbox("chkFactoryManager")
        self._director_checkbox.setEnabled(False)
        self._factory_manager_checkbox.setEnabled(False)
        self._director_checkbox.setToolTip("Corporation role details will be loaded after ESI data sync is implemented.")
        self._factory_manager_checkbox.setToolTip(
            "Corporation role details will be loaded after ESI data sync is implemented."
        )

        self._add_character_button = self._find_button("btnAddCharacter")
        self._delete_character_button = self._find_button("btnDeleteCharacter")
        self._default_character_button = self._find_button("btnSelectDefaultChar")
        self._refresh_token_button = self._find_button("btnRefreshToken")
        self._copy_access_token_button = self._find_button("btnCopyAccesToken")
        self._copy_corp_id_button = self._find_button("btnCopyCorpID")
        self._copy_character_id_button = self._find_button("btnCopyCharacterID")
        self._copy_all_button = self._find_button("btnCopyAll")
        self._close_button = self._find_button("btnClose")

        self._add_character_button.clicked.connect(self._open_add_character_window)
        self._delete_character_button.clicked.connect(self._delete_selected_character)
        self._default_character_button.clicked.connect(self._set_default_character)
        self._refresh_token_button.clicked.connect(self._refresh_selected_character)
        self._copy_access_token_button.clicked.connect(lambda: self._copy_text(self._access_token_field.text()))
        self._copy_corp_id_button.clicked.connect(lambda: self._copy_text(self._corporation_id_field.text()))
        self._copy_character_id_button.clicked.connect(lambda: self._copy_text(self._character_id_field.text()))
        self._copy_all_button.clicked.connect(self._copy_selected_token_data)
        self._close_button.clicked.connect(self.window.close)
        self._accounts_tree.currentItemChanged.connect(self._handle_account_selection_changed)
        self.window.closeEvent = self._close_event

        self._refresh_accounts()

    def show(self) -> None:
        self._refresh_accounts(select_character_id=self._selected_character_id() or self._character_service.get_default_character_id())
        _show_window(self.window)

    def _open_add_character_window(self) -> None:
        if self._add_character_window is None:
            self._add_character_window = AddCharacterWindowController(
                config=self._config,
                auth_service=self._auth_service,
                on_authorized=self._handle_character_authorized,
                parent=self.window,
            )

        self._add_character_window.show()

    def _handle_character_authorized(self, character: AuthenticatedCharacter) -> None:
        try:
            managed_character = self._character_service.handle_authorized_character(character)
            select_character_id = managed_character.character_id
        except Exception as error:
            QMessageBox.warning(
                self.window,
                "Character Data",
                (
                    "The character was authorized, but public ESI profile data could not be synchronized yet.\n\n"
                    f"{error}"
                ),
            )
            select_character_id = character.character_id

        self._refresh_accounts(select_character_id=select_character_id)

    def _refresh_accounts(self, select_character_id: int | None = None) -> None:
        characters = self._character_service.list_managed_characters()
        self._managed_characters = {character.character_id: character for character in characters}
        self._accounts_tree.clear()
        selected_item: QTreeWidgetItem | None = None
        preferred_character_id = select_character_id if select_character_id is not None else self._character_service.get_default_character_id()

        for character in characters:
            item = QTreeWidgetItem([self._format_account_label(character)])
            item.setData(0, Qt.ItemDataRole.UserRole, character.character_id)
            self._accounts_tree.addTopLevelItem(item)
            if preferred_character_id is not None and character.character_id == preferred_character_id:
                selected_item = item

        if selected_item is None and self._accounts_tree.topLevelItemCount() > 0:
            selected_item = self._accounts_tree.topLevelItem(0)

        if selected_item is not None:
            self._accounts_tree.setCurrentItem(selected_item)
        else:
            self._clear_details()
            self._update_action_state(None)

    @Slot(object, object)
    def _handle_account_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        _previous: QTreeWidgetItem | None,
    ) -> None:
        if current is None:
            self._clear_details()
            self._update_action_state(None)
            return

        character_id = current.data(0, Qt.ItemDataRole.UserRole)
        if character_id is None:
            self._clear_details()
            self._update_action_state(None)
            return

        managed_character = self._managed_characters.get(int(character_id))
        if managed_character is None:
            self._clear_details()
            self._update_action_state(None)
            return

        if managed_character.corporation_id is None:
            try:
                synchronized_character = self._character_service.get_managed_character(int(character_id), sync_if_missing=True)
            except Exception:
                synchronized_character = None
            if synchronized_character is not None:
                managed_character = synchronized_character
                self._managed_characters[managed_character.character_id] = managed_character

        self._bind_managed_character(managed_character)
        self._update_action_state(managed_character)

    def _refresh_selected_character(self) -> None:
        character_id = self._selected_character_id()
        if character_id is None:
            QMessageBox.information(self.window, "Refresh Token", "Select a character first.")
            return

        try:
            refreshed = self._character_service.refresh_character_data(character_id)
        except Exception as error:
            QMessageBox.warning(self.window, "Refresh Token", str(error))
            return

        self._refresh_accounts(select_character_id=refreshed.character_id)

    def _set_default_character(self) -> None:
        character_id = self._selected_character_id()
        if character_id is None:
            QMessageBox.information(self.window, "Default Character", "Select a character first.")
            return

        try:
            default_character = self._character_service.set_default_character(character_id)
        except Exception as error:
            QMessageBox.warning(self.window, "Default Character", str(error))
            return

        self._refresh_accounts(select_character_id=default_character.character_id)

    def _delete_selected_character(self) -> None:
        character_id = self._selected_character_id()
        if character_id is None:
            QMessageBox.information(self.window, "Delete Character", "Select a character first.")
            return

        selected_name = self._accounts_tree.currentItem().text(0)
        answer = QMessageBox.question(
            self.window,
            "Delete Character",
            f"Remove '{selected_name}' from the local ESI authorization store?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._character_service.revoke_character(character_id)
        self._refresh_accounts()

    def _bind_managed_character(self, character: ManagedCharacter) -> None:
        self._access_token_field.setText(character.access_token)
        self._character_id_field.setText(str(character.character_id))
        self._corporation_id_field.setText("" if character.corporation_id is None else str(character.corporation_id))
        self._refresh_token_field.setText(character.refresh_token or "")
        self._access_token_expiry_field.setText(character.expires_at.astimezone(timezone.utc).isoformat())
        self._director_checkbox.setChecked(False)
        self._factory_manager_checkbox.setChecked(False)
        self._scopes_tree.clear()
        for scope in character.scopes:
            self._scopes_tree.addTopLevelItem(QTreeWidgetItem([scope]))

    def _copy_selected_token_data(self) -> None:
        scopes = [self._scopes_tree.topLevelItem(index).text(0) for index in range(self._scopes_tree.topLevelItemCount())]
        payload = "\n".join(
            (
                f"Character ID: {self._character_id_field.text()}",
                f"Corporation ID: {self._corporation_id_field.text()}",
                f"Access Token: {self._access_token_field.text()}",
                f"Refresh Token: {self._refresh_token_field.text()}",
                f"Access Token Expiration Date: {self._access_token_expiry_field.text()}",
                "Scopes:",
                *scopes,
            )
        )
        self._copy_text(payload)

    def _copy_text(self, text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)

    def _selected_character_id(self) -> int | None:
        item = self._accounts_tree.currentItem()
        if item is None:
            return None

        value = item.data(0, Qt.ItemDataRole.UserRole)
        if value is None:
            return None

        return int(value)

    def _update_action_state(self, character: ManagedCharacter | None) -> None:
        has_character = character is not None
        self._delete_character_button.setEnabled(has_character)
        self._default_character_button.setEnabled(has_character and not character.is_default if character is not None else False)
        self._refresh_token_button.setEnabled(has_character)
        self._copy_access_token_button.setEnabled(has_character)
        self._copy_character_id_button.setEnabled(has_character)
        self._copy_all_button.setEnabled(has_character)
        self._copy_corp_id_button.setEnabled(has_character and bool(self._corporation_id_field.text()))

    def _clear_details(self) -> None:
        self._access_token_field.clear()
        self._character_id_field.clear()
        self._corporation_id_field.clear()
        self._refresh_token_field.clear()
        self._access_token_expiry_field.clear()
        self._director_checkbox.setChecked(False)
        self._factory_manager_checkbox.setChecked(False)
        self._scopes_tree.clear()

    @staticmethod
    def _format_account_label(character: ManagedCharacter) -> str:
        label = f"{character.character_name} ({character.character_id})"
        if character.is_default:
            return f"{label} [Default]"
        return label

    def _close_event(self, event: QCloseEvent) -> None:
        if self._add_character_window is not None and self._add_character_window.is_busy:
            QMessageBox.information(
                self.window,
                "ESI SSO",
                "Character authorization is still in progress. Finish or cancel the browser flow first.",
            )
            event.ignore()
            return

        if self._add_character_window is not None:
            self._add_character_window.close()

        event.accept()

    def _find_button(self, object_name: str) -> QPushButton:
        button = self.window.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in character management UI.")

        return button

    def _find_tree_widget(self, object_name: str) -> QTreeWidget:
        tree = self.window.findChild(QTreeWidget, object_name)
        if tree is None:
            raise LookupError(f"QTreeWidget '{object_name}' was not found in character management UI.")

        return tree

    def _find_line_edit(self, object_name: str) -> QLineEdit:
        line_edit = self.window.findChild(QLineEdit, object_name)
        if line_edit is None:
            raise LookupError(f"QLineEdit '{object_name}' was not found in character management UI.")

        return line_edit

    def _find_checkbox(self, object_name: str) -> QCheckBox:
        checkbox = self.window.findChild(QCheckBox, object_name)
        if checkbox is None:
            raise LookupError(f"QCheckBox '{object_name}' was not found in character management UI.")

        return checkbox
