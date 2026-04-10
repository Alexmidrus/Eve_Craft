from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Generic, TypeVar

from PySide6.QtCore import QObject, Signal, Slot

from iph2.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)

TaskResultT = TypeVar("TaskResultT")


class BackgroundTaskWorker(QObject, Generic[TaskResultT]):
    progress_changed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, task: Callable[[Callable[[OperationProgress], None]], TaskResultT]) -> None:
        super().__init__()
        self._task = task

    @Slot()
    def run(self) -> None:
        try:
            result = self._task(self._emit_progress)
        except Exception as exc:  # pragma: no cover - exercised through UI flow
            LOGGER.exception("Background task failed.")
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()

    def _emit_progress(self, progress: OperationProgress) -> None:
        self.progress_changed.emit(progress)
