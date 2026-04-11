from __future__ import annotations

import unittest

try:
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError:  # pragma: no cover - dependency gate
    QApplication = None

from eve_craft.app.config import load_app_config
from eve_craft.platform.characters.presentation.windows import ManageAccountsWindowController


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class CharacterManagementWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._application = QApplication.instance() or QApplication([])

    def test_manage_accounts_window_stays_top_level_when_parented(self) -> None:
        config = load_app_config()
        parent = QWidget()
        controller = ManageAccountsWindowController(config=config, parent=parent)

        self.assertTrue(controller.window.isWindow())
        self.assertEqual(parent, controller.window.parentWidget())

        controller.window.close()
        parent.close()

    def test_add_character_button_opens_the_add_character_window(self) -> None:
        config = load_app_config()
        controller = ManageAccountsWindowController(config=config)

        controller._add_character_button.click()

        self.assertIsNotNone(controller._add_character_window)
        self.assertTrue(controller._add_character_window.window.isWindow())
        self.assertEqual(controller.window, controller._add_character_window.window.parentWidget())

        controller._add_character_window.close()
        controller.window.close()
