from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QLabel, QMessageBox, QProgressBar, QPushButton, QWidget

from eve_craft.app.config import AppConfig
from eve_craft.app.presentation.background_tasks import BackgroundTaskWorker
from eve_craft.app.presentation.ui_loader import load_ui_widget
from eve_craft.app.startup import ApplicationStartupService, StartupSummary
from eve_craft.shared.progress import OperationProgress


class StartupSplashWindow(QObject):
    def __init__(
        self,
        config: AppConfig,
        startup_service: ApplicationStartupService,
        on_success: Callable[[StartupSummary], None],
        on_failure: Callable[[str], None],
    ) -> None:
        super().__init__()
        self._config = config
        self._startup_service = startup_service
        self._on_success = on_success
        self._on_failure = on_failure
        self.widget = load_ui_widget(config.paths.startup_splash_ui)
        self._status_label = self._find_label("statusLabel")
        self._details_label = self._find_label("detailsLabel")
        self._progress_bar = self._find_progress_bar("startupProgressBar")
        self._close_button = self._find_button("closeButton")
        self._close_button.hide()
        self._close_button.clicked.connect(self.widget.close)
        self._thread: QThread | None = None
        self._worker: BackgroundTaskWorker[StartupSummary] | None = None

        if config.paths.icon_file.exists():
            self.widget.setWindowIcon(QIcon(str(config.paths.icon_file)))

        self.widget.closeEvent = self._close_event

    def show(self) -> None:
        self.widget.show()

    def start(self) -> None:
        self._thread = QThread()
        self._worker = BackgroundTaskWorker(self._startup_service.run)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress_changed.connect(self._apply_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.succeeded.connect(self._handle_success, Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._handle_failure, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._task_finished)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot()
    def _task_finished(self) -> None:
        self._thread = None
        self._worker = None

    @Slot(object)
    def _apply_progress(self, progress: OperationProgress) -> None:
        self._status_label.setText(progress.message)
        self._details_label.setText(progress.detail or progress.stage.replace("_", " ").title())

        if progress.indeterminate or progress.percent is None:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress.clamp_percent() or 0)

    @Slot(object)
    def _handle_success(self, summary: StartupSummary) -> None:
        self.widget.hide()
        self._on_success(summary)

    @Slot(str)
    def _handle_failure(self, message: str) -> None:
        self._status_label.setText("Startup failed")
        self._details_label.setText(message)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._close_button.show()
        QMessageBox.critical(self.widget, "Startup Error", message)
        self._on_failure(message)

    def _close_event(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            event.ignore()
            return

        event.accept()

    def _find_label(self, object_name: str) -> QLabel:
        label = self.widget.findChild(QLabel, object_name)
        if label is None:
            raise LookupError(f"QLabel '{object_name}' was not found in startup splash UI.")

        return label

    def _find_progress_bar(self, object_name: str) -> QProgressBar:
        progress_bar = self.widget.findChild(QProgressBar, object_name)
        if progress_bar is None:
            raise LookupError(f"QProgressBar '{object_name}' was not found in startup splash UI.")

        return progress_bar

    def _find_button(self, object_name: str) -> QPushButton:
        button = self.widget.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in startup splash UI.")

        return button

