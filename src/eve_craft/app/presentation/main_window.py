from __future__ import annotations

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from eve_craft.app.config import AppConfig
from eve_craft.app.container import AppContainer
from eve_craft.app.navigation import MainTabNavigator
from eve_craft.app.presentation.ui_loader import load_main_window
from eve_craft.platform.characters.presentation.windows import ManageAccountsWindowController
from eve_craft.platform.sde.presentation.dialog import SdeUpdateDialogController


class MainWindowShell:
    def __init__(self, config: AppConfig, container: AppContainer) -> None:
        self._config = config
        self._container = container
        self.window = load_main_window(config.paths.main_window_ui)
        self._tab_widget = self._find_required_tab_widget("tabWidget")
        self._navigator = MainTabNavigator(self._tab_widget)
        self._character_management_window: ManageAccountsWindowController | None = None
        self._sde_dialog: SdeUpdateDialogController | None = None

        self._register_module_tabs()
        self._configure_window()
        self._connect_actions()
        self._connect_tab_events()
        self._update_status_for_current_tab()

    def show(self) -> None:
        self.window.show()

    def _register_module_tabs(self) -> None:
        for module in self._container.module_registry.feature_modules():
            self._navigator.register_module_tab(module)

    def _configure_window(self) -> None:
        self.window.setWindowTitle(self._config.application_name)

        if self._config.paths.icon_file.exists():
            icon = QIcon(str(self._config.paths.icon_file))
            self.window.setWindowIcon(icon)

            if self._navigator.has_tab("industry"):
                self._tab_widget.setTabIcon(self._navigator.tab_index("industry"), icon)

    def _connect_actions(self) -> None:
        self._action("actionManage_character").triggered.connect(self._open_character_management)
        self._action("actionSDE").triggered.connect(self._open_sde_center)
        self._action("actionESI_Status").triggered.connect(self._open_esi_status)
        self._action("actionView_Log").triggered.connect(self._show_log_location)
        self._action("actionAssets_profile").triggered.connect(self._open_assets_profile)
        self._action("actionIndustry_profile").triggered.connect(self._open_industry_profile)

    def _connect_tab_events(self) -> None:
        self._tab_widget.currentChanged.connect(self._update_status_for_current_tab)

    def _update_status_for_current_tab(self, *_args) -> None:
        tab_name = self._navigator.current_tab_name() or "Unknown"
        self.window.statusBar().showMessage(f"Ready. Active module: {tab_name}")

    def _open_character_management(self) -> None:
        if self._character_management_window is None:
            self._character_management_window = ManageAccountsWindowController(
                config=self._config,
                parent=self.window,
            )

        self._character_management_window.show()
        self.window.statusBar().showMessage("Character management opened.", 4000)

    def _open_sde_center(self) -> None:
        if self._sde_dialog is None:
            self._sde_dialog = SdeUpdateDialogController(
                config=self._config,
                sde_service=self._container.sde,
                parent=self.window,
            )

        self._sde_dialog.show()

    def _open_esi_status(self) -> None:
        self._show_info("ESI", self._container.esi.describe_status())

    def _show_log_location(self) -> None:
        log_file = self._config.paths.logs_dir / "eve_craft.log"
        self._show_info("Log", f"Application log file: {log_file}")

    def _open_assets_profile(self) -> None:
        message = self._container.settings.describe_profile("assets")
        self._show_info("Assets Profile", message)

    def _open_industry_profile(self) -> None:
        message = self._container.settings.describe_profile("industry")
        self._show_info("Industry Profile", message)

    def _action(self, object_name: str) -> QAction:
        action = self.window.findChild(QAction, object_name)
        if action is None:
            raise LookupError(f"Action with objectName='{object_name}' was not found in the UI.")

        return action

    def _find_required_tab_widget(self, object_name: str) -> QTabWidget:
        tab_widget = self.window.findChild(QTabWidget, object_name)
        if tab_widget is None:
            raise LookupError(f"QTabWidget with objectName='{object_name}' was not found in the UI.")

        return tab_widget

    def _show_info(self, title: str, text: str) -> None:
        self.window.statusBar().showMessage(text, 8000)
        QMessageBox.information(self.window, title, text)

