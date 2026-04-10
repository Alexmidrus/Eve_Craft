from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFile, QFileInfo, QIODevice
from PySide6.QtGui import QAction, QIcon
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from iph2.app.config import AppConfig
from iph2.app.container import AppContainer
from iph2.app.navigation import MainTabNavigator


class MainWindowShell:
    def __init__(self, config: AppConfig, container: AppContainer) -> None:
        self._config = config
        self._container = container
        self.window = self._load_window(config.paths.main_window_ui)
        self._tab_widget = self._find_required_tab_widget("tabWidget")
        self._navigator = MainTabNavigator(self._tab_widget)

        self._register_module_tabs()
        self._configure_window()
        self._connect_actions()
        self._connect_tab_events()
        self._update_status_for_current_tab()

    def show(self) -> None:
        self.window.show()

    def _load_window(self, ui_path: Path) -> QMainWindow:
        if not ui_path.exists():
            raise FileNotFoundError(f"Main window UI file was not found: {ui_path}")

        loader = QUiLoader()
        loader.setWorkingDirectory(QFileInfo(str(ui_path)).dir())

        ui_file = QFile(str(ui_path))
        if not ui_file.open(QIODevice.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Unable to open UI file: {ui_path}")

        try:
            loaded_window = loader.load(ui_file)
        finally:
            ui_file.close()

        if loaded_window is None or not isinstance(loaded_window, QMainWindow):
            raise RuntimeError("The main UI file did not produce a QMainWindow instance.")

        return loaded_window

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
        self._show_info("Character", self._container.characters.describe_management())

    def _open_sde_center(self) -> None:
        self._show_info("SDE", self._container.sde.describe_status())

    def _open_esi_status(self) -> None:
        self._show_info("ESI", self._container.esi.describe_status())

    def _show_log_location(self) -> None:
        log_file = self._config.paths.logs_dir / "iph2.log"
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
