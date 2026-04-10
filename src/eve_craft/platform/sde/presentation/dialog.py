"""Qt controller responsible for checking and updating the local SDE build."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Qt, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QWidget

from eve_craft.app.config import AppConfig
from eve_craft.app.presentation.background_tasks import BackgroundTaskWorker
from eve_craft.app.presentation.ui_loader import load_dialog
from eve_craft.platform.sde.domain.models import SdeStatus, SdeSyncResult
from eve_craft.platform.sde.service import SdeService
from eve_craft.shared.progress import OperationProgress


class SdeUpdateDialogController(QObject):
    """Drive the modal dialog that displays SDE status and runs background updates."""

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
        """Show the dialog and bring it to the front of the current window stack."""

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _load_cached_status(self) -> None:
        """Populate the dialog from the locally cached status without network traffic."""

        status = self._sde_service.get_status(refresh_remote=False)
        self._apply_status(status)
        self._append_log(status.message)

    def _check_status(self) -> None:
        """Refresh remote status information in a background thread."""

        self._start_task(
            task=lambda _report: self._sde_service.get_status(refresh_remote=True),
            success_handler=self._handle_status_result,
        )

    def _update_sde(self) -> None:
        """Trigger an SDE update workflow in a background thread."""

        self._start_task(
            task=lambda report: self._sde_service.update(report_progress=report, force=False),
            success_handler=self._handle_sync_result,
        )

    def _start_task(
        self,
        task: Callable[[Callable[[OperationProgress], None]], object],
        success_handler: Callable[[object], None],
    ) -> None:
        """Start a worker thread for a long-running SDE operation."""

        if self._busy:
            return

        self._busy = True
        self._set_buttons_enabled(False)
        self._thread = QThread()
        self._worker = BackgroundTaskWorker(task)
        self._worker.moveToThread(self._thread)

        # All worker signals are marshalled back to the UI thread before touching widgets.
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
        """Restore interactive UI state after a background task completes."""

        self._busy = False
        self._set_buttons_enabled(True)
        self._thread = None
        self._worker = None

    @Slot(object)
    def _handle_status_result(self, status: SdeStatus) -> None:
        """Apply a refreshed status snapshot to the dialog widgets."""

        self._apply_status(status)
        self._append_log(status.message)

    @Slot(object)
    def _handle_sync_result(self, result: SdeSyncResult) -> None:
        """Apply the outcome of a synchronization run to the dialog."""

        self._apply_status(result.status)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(100 if result.updated else self._progress_bar.value())
        self._append_log(result.status.message)
        for warning in result.warnings:
            self._append_log(warning)

    @Slot(str)
    def _handle_failure(self, message: str) -> None:
        """Show an unrecoverable worker error in the status area and log."""

        self._status_label.setText(message)
        self._append_log(message)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

    @Slot(object)
    def _apply_progress(self, progress: OperationProgress) -> None:
        """Render progress updates emitted by background SDE workflows."""

        self._status_label.setText(progress.message)
        self._append_log(progress.detail or progress.message)

        if progress.indeterminate or progress.percent is None:
            self._progress_bar.setRange(0, 0)
        else:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress.clamp_percent() or 0)

    def _apply_status(self, status: SdeStatus) -> None:
        """Render a status snapshot into the dialog labels."""

        self._installed_build_label.setText(
            str(status.installed.build_number) if status.installed is not None else "Not installed"
        )
        self._latest_build_label.setText(str(status.latest.build_number) if status.latest is not None else "Unknown")
        self._release_date_label.setText(
            status.latest.release_date.isoformat() if status.latest is not None else "-"
        )
        self._status_label.setText(status.message)

    def _append_log(self, message: str) -> None:
        """Append a single log line to the dialog output pane."""

        self._log_output.appendPlainText(message)

    def _set_buttons_enabled(self, enabled: bool) -> None:
        """Toggle the dialog controls while background work is in progress."""

        self._check_button.setEnabled(enabled)
        self._update_button.setEnabled(enabled)
        self._close_button.setEnabled(enabled)

    def _close_event(self, event: QCloseEvent) -> None:
        """Prevent closing the dialog while a background operation is still active."""

        if self._busy:
            event.ignore()
            return

        event.accept()

    def _find_label(self, object_name: str) -> QLabel:
        """Resolve a required label from the loaded Qt Designer form."""

        label = self.dialog.findChild(QLabel, object_name)
        if label is None:
            raise LookupError(f"QLabel '{object_name}' was not found in SDE dialog UI.")

        return label

    def _find_progress_bar(self, object_name: str) -> QProgressBar:
        """Resolve the progress bar from the loaded Qt Designer form."""

        progress_bar = self.dialog.findChild(QProgressBar, object_name)
        if progress_bar is None:
            raise LookupError(f"QProgressBar '{object_name}' was not found in SDE dialog UI.")

        return progress_bar

    def _find_log_output(self, object_name: str) -> QPlainTextEdit:
        """Resolve the read-only log pane from the loaded Qt Designer form."""

        log_output = self.dialog.findChild(QPlainTextEdit, object_name)
        if log_output is None:
            raise LookupError(f"QPlainTextEdit '{object_name}' was not found in SDE dialog UI.")

        return log_output

    def _find_button(self, object_name: str) -> QPushButton:
        """Resolve a required button from the loaded Qt Designer form."""

        button = self.dialog.findChild(QPushButton, object_name)
        if button is None:
            raise LookupError(f"QPushButton '{object_name}' was not found in SDE dialog UI.")

        return button

