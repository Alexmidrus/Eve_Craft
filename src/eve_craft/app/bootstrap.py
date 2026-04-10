from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from eve_craft.app.config import load_app_config
from eve_craft.app.container import build_container
from eve_craft.app.module_registry import build_default_registry
from eve_craft.app.presentation.main_window import MainWindowShell
from eve_craft.app.presentation.startup_splash import StartupSplashWindow
from eve_craft.app.startup import ApplicationStartupService, StartupSummary
from eve_craft.platform.logging.setup import configure_logging


def bootstrap_application() -> int:
    config = load_app_config()
    configure_logging(config.paths.logs_dir)

    application = QApplication(sys.argv)
    application.setApplicationName(config.application_name)
    application.setOrganizationName(config.organization_name)

    module_registry = build_default_registry()
    container = build_container(config, module_registry)
    startup_service = ApplicationStartupService(container)
    state: dict[str, object] = {}

    def open_main_window(_summary: StartupSummary) -> None:
        main_window = MainWindowShell(config=config, container=container)
        state["main_window"] = main_window
        main_window.show()

    def handle_startup_failure(_message: str) -> None:
        application.quit()

    splash = StartupSplashWindow(
        config=config,
        startup_service=startup_service,
        on_success=open_main_window,
        on_failure=handle_startup_failure,
    )
    state["splash"] = splash
    splash.show()
    splash.start()

    return application.exec()

