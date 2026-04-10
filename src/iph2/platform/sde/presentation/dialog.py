from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QWidget

from iph2.app.config import AppConfig
from iph2.app.presentation.background_tasks import BackgroundTaskWorker
from iph2.app.presentation.ui_loader import load_dialog
from iph2.platform.sde.domain.models import SdeStatus, SdeSyncResult
from iph2.platform.sde.service import SdeService
from iph2.shared.progress import OperationProgress


class SdeUpdateDialogController(QObject):
    def __init__(self, config: AppConfig, sde_service: SdeService, parent: QWidget | None = None) -> None:
        super().__init__()
        self._config = config
        self._sde_service = sde_service
        self.dialog = load_dialog(config.paths.sde_update_dialog_ui)
        if parent is not None:
            self.dialog.setParent(parent, self.dialog.windowFlags())
            self.dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.dialog.setModal(True)

        self._installed_build_label = self._find_label("installedBuildValueLabel")
        self._latest_build_label = self._find_label("latestBuildValueLabel")
        self._release_date_label = self._find_label("releaseDateValueLabel")
        self._status_label = self._find_label("statusValueLabel")
        self._progress_bar = self._find_progress_bar("updateProgressBar")
        self._log_output = self._find_log_output("logOutput")
        self._check_button = self._find_button("checkButton")
        self._update_button = self._find_button("updateButton")
        self._close_button = self._find_button("closeButton")

        self._thread: QThread | None = None
        self._worker: BackgroundTaskWorker[object] | None = None
        self._busy = False

        if config.paths.icon_file.exists():
            self.dialog.setWindowIcon(QIcon(str(config.paths.icon_file)))

        self._check_button.clicked.connect(self._check_status)
        self._update_button.clicked.connect(self._update_sde)
        self._close_button.clicked.connect(self.dialog.accept)
        self.dialog.closeEvent = self._close_event

        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._load_cached_status()

    def show(self) -> None:
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _load_cached_status(self) -> None:
        status = self._sde_service.get_status(refresh_remote=False)
        self._apply_status(status)
        self._append_log(status.message)

    def _check_status(self) -> None:
        self._start_task(
            task=lambda _report: self._sde_service.get_status(refresh_remote=True),
            success_handler=self._handle_status_result,
        )

    def _update_sde(self) -> None:
        self._start_task(
            task=lambda report: self._sde_service.update(report_progress=report, force=False),
            success_handler=self._handle_sync_result,
        )

    def _start_task(
        self,
        task: Callable[[Callable[[OperationProgress], None]], object],
        success_handler: Callable[[object], None],
    ) -> None:
        if self._busy:
            return

        self._busy = True
        self._set_buttons_enabled(False)
        self._thread = QThread()
        self._worker = BackgroundTaskWorker(task)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress_changed.connect(self._apply_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.succeeded.connect(success_handler, Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._handle_failure, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._task_finished)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    @Slot()
    def _task_finished(self) -> None:
        self._busy = False
        self._set_buttons_enabled(True)
        self._thread = None
        self._worker = None

    @Slot(object)
    def _handle_status_result(self, status: SdeStatus) -> None:
        self._apply_status(status)
        self._append_log(status.message)

    @Slot(object)
    def _handle_sync_result(self, result: SdeSyncResult) -> None:
        self._apply_status(result.status)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100 if result.updated else self._progress_bar.value())
        self._append_log(result.status.message)
        for warning in result.warnings:
            self._append_log(warning)

    @Slot(str)
    def _handle_failure(self, message: str) -> None:
        self._status_label.setText(message)
        self._append_log(message)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

    @Slot(object)
    def _apply_progress(self, progress: OperationProgress) -> None:
        self._status_label.setText(progress.message)
        self._append_log(progress.detail or progress.message)

        if progress.indeterminate or progress.percent is None:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress.clamp_percent() or 0)

    def _apply_status(self, status: SdeStatus) -> None:
        self._installed_build_label.setText(
            str(status.installed.build_number) if status.installed is not None else "Not installed"
        )
        self._latest_build_label.setText(str(status.latest.build_number) if status.latest is not None else "Unknown")
        self._release_date_label.setText(
            status.latest.release_date.isoformat() if status.latest is not None else "-"
        )
        self._status_label.setText(status.message)

    def _append_log(self, message: str) -> None:
        self._log_output.appendPlainText(message)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._check_button.setEnabled(enabled)
        self._update_button.setEnabled(enabled)
        self._close_button.setEnabled(enabled)

    def _close_event(self, event: QCloseEvent) -> None:
        if self._busy:
            event.ignore()
            return

        event.accept()

    def _find_label(self, object_name: str) -> QLabel:
        label = self.dialog.findChild(QLabel, object_name)
        if label is None:
            raise LookupError(f"QLabel '{object_name}' was not found in SDE dialog UI.")

        return label

    def _find_progress_bar(self, object_name: str) -> QProgressBar:
        progress_bar = self.dialog.findChild(QProgressBar, object_name)
        if progress_bar is None:
            raise LookupError(f"QProgressBar '{object_name}' was not found in SDE dialog UI.")

        return progress_bar

    def _find_log_output(self, object_name: str) -> QPlainTextEdit:
        log_output = self.dialog.findChild(QPlainTextEdit, object_name)
        if log_output is None:
            raise LookupError(f"QPlainTextEdit '{object_name}' was not found in SDE dialog UI.")

        return log_output

    def _find_button(self, object_name: str) -> QPushButton:
        button = self.dialog.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in SDE dialog UI.")

        return button
