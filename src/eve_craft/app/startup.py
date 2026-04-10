from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from eve_craft.app.container import AppContainer
from eve_craft.platform.sde.domain.models import SdeSyncResult
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StartupSummary:
    sde_result: SdeSyncResult
    warnings: tuple[str, ...] = field(default_factory=tuple)


class ApplicationStartupService:
    def __init__(self, container: AppContainer) -> None:
        self._container = container

    def run(self, report_progress: Callable[[OperationProgress], None]) -> StartupSummary:
        LOGGER.info("Application startup started.")
        report_progress(
            OperationProgress(
                stage="startup",
                message="Preparing runtime environment",
                percent=5,
            )
        )

        self._container.app_database.ensure_initialized()
        LOGGER.info("Application database initialized.")
        report_progress(
            OperationProgress(
                stage="app_db",
                message="Application database is ready",
                percent=15,
            )
        )

        sde_result = self._container.sde.ensure_ready(
            report_progress=self._startup_sde_progress_adapter(report_progress)
        )
        LOGGER.info("SDE readiness check completed. Updated=%s", sde_result.updated)

        report_progress(
            OperationProgress(
                stage="startup_complete",
                message="Startup checks completed",
                percent=100,
            )
        )
        return StartupSummary(
            sde_result=sde_result,
            warnings=sde_result.warnings,
        )

    def _startup_sde_progress_adapter(
        self,
        report_progress: Callable[[OperationProgress], None],
    ) -> Callable[[OperationProgress], None]:
        def adapter(progress: OperationProgress) -> None:
            percent = progress.clamp_percent()
            mapped_percent = 15 if percent is None else 15 + int(percent * 0.8)
            report_progress(
                OperationProgress(
                    stage=progress.stage,
                    message=progress.message,
                    percent=mapped_percent,
                    detail=progress.detail,
                    indeterminate=progress.indeterminate,
                )
            )

        return adapter

