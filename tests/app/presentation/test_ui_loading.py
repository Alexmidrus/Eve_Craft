from __future__ import annotations

import unittest

try:
    from PySide6.QtWidgets import QApplication, QTabWidget, QWidget
except ImportError:  # pragma: no cover - dependency gate
    QApplication = None

from eve_craft.app.config import load_app_config
from eve_craft.app.navigation import MainTabNavigator
from eve_craft.app.presentation.ui_loader import load_dialog, load_main_window, load_ui_widget
from eve_craft.modules.industry.module import build_module as build_industry_module
from eve_craft.modules.market.module import build_module as build_market_module
from eve_craft.platform.sde.domain.models import SdeStatus
from eve_craft.platform.sde.presentation.dialog import SdeUpdateDialogController


class _FakeSdeService:
    def __init__(self) -> None:
        self.call_count = 0

    def get_status(self, refresh_remote: bool = False) -> SdeStatus:
        self.call_count += 1
        return SdeStatus(
            installed=None,
            latest=None,
            update_available=False,
            available=False,
            message="Not installed",
        )


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class UiLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._application = QApplication.instance() or QApplication([])

    def test_can_load_splash_and_sde_dialog_ui(self) -> None:
        config = load_app_config()

        splash = load_ui_widget(config.paths.startup_splash_ui)
        dialog = load_dialog(config.paths.sde_update_dialog_ui)
        main_window = load_main_window(config.paths.main_window_ui)
        manage_accounts = load_ui_widget(config.paths.manage_accounts_ui)
        add_character = load_ui_widget(config.paths.add_character_ui)

        self.assertEqual("StartupSplash", splash.objectName())
        self.assertEqual("SdeUpdateDialog", dialog.objectName())
        self.assertIsNotNone(main_window.findChild(QTabWidget, "tabMain"))
        self.assertEqual("frmManageAccounts", manage_accounts.objectName())
        self.assertEqual("frmAddCharacter", add_character.objectName())

    def test_main_window_supports_registered_feature_tabs(self) -> None:
        config = load_app_config()
        main_window = load_main_window(config.paths.main_window_ui)
        tab_widget = main_window.findChild(QTabWidget, "tabMain")

        self.assertIsNotNone(tab_widget)

        navigator = MainTabNavigator(tab_widget)
        navigator.register_module_tab(build_industry_module())
        navigator.register_module_tab(build_market_module())

        self.assertTrue(navigator.has_tab("industry"))
        self.assertTrue(navigator.has_tab("market"))

    def test_sde_dialog_controller_keeps_dialog_as_top_level_window(self) -> None:
        config = load_app_config()
        parent = QWidget()
        service = _FakeSdeService()
        controller = SdeUpdateDialogController(
            config=config,
            sde_service=service,
            parent=parent,
        )

        self.assertTrue(controller.dialog.isWindow())
        self.assertEqual(parent, controller.dialog.parentWidget())
        self.assertEqual(0, service.call_count)

