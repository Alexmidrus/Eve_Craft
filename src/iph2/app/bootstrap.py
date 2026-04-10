from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from iph2.app.config import load_app_config
from iph2.app.container import build_container
from iph2.app.module_registry import build_default_registry
from iph2.app.presentation.main_window import MainWindowShell
from iph2.platform.logging.setup import configure_logging


def bootstrap_application() -> int:
    config = load_app_config()
    configure_logging(config.paths.logs_dir)

    application = QApplication(sys.argv)
    application.setApplicationName(config.application_name)
    application.setOrganizationName(config.organization_name)

    module_registry = build_default_registry()
    container = build_container(config, module_registry)
    main_window = MainWindowShell(config=config, container=container)
    main_window.show()

    return application.exec()
