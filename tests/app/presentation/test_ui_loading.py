from __future__ import annotations

import unittest

try:
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError:  # pragma: no cover - dependency gate
    QApplication = None

from iph2.app.config import load_app_config
from iph2.app.presentation.ui_loader import load_dialog, load_ui_widget
from iph2.platform.sde.domain.models import SdeStatus
from iph2.platform.sde.presentation.dialog import SdeUpdateDialogController


class _FakeSdeService:
    def get_status(self, refresh_remote: bool = False) -> SdeStatus:
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

        self.assertEqual("StartupSplash", splash.objectName())
        self.assertEqual("SdeUpdateDialog", dialog.objectName())

    def test_sde_dialog_controller_keeps_dialog_as_top_level_window(self) -> None:
        config = load_app_config()
        parent = QWidget()
        controller = SdeUpdateDialogController(
            config=config,
            sde_service=_FakeSdeService(),
            parent=parent,
        )

        self.assertTrue(controller.dialog.isWindow())
        self.assertEqual(parent, controller.dialog.parentWidget())
