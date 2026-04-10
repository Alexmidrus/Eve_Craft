from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eve_craft.app.config import AppConfig
from eve_craft.platform.sde.application.synchronizer import SdeSynchronizer
from eve_craft.platform.sde.domain.models import SdeStatus, SdeSyncResult
from eve_craft.platform.sde.infrastructure.client import EveStaticDataClient
from eve_craft.platform.sde.infrastructure.importer import SdeImporter
from eve_craft.platform.sde.infrastructure.repository import SdeMetadataRepository
from eve_craft.shared.progress import OperationProgress


class SdeService:
    def __init__(self, config: AppConfig) -> None:
        self._repository = SdeMetadataRepository(config.paths.sde_database_path)
        self._synchronizer = SdeSynchronizer(
            repository=self._repository,
            client=EveStaticDataClient(),
            importer=SdeImporter(config.paths.temporary_dir),
            downloads_dir=config.paths.downloads_dir,
        )

    @property
    def database_path(self) -> Path:
        return self._repository.database_path

    def get_status(self, refresh_remote: bool = False) -> SdeStatus:
        return self._synchronizer.get_status(refresh_remote=refresh_remote)

    def ensure_ready(self, report_progress: Callable[[OperationProgress], None]) -> SdeSyncResult:
        return self._synchronizer.ensure_ready(report_progress=report_progress)

    def update(self, report_progress: Callable[[OperationProgress], None], force: bool = False) -> SdeSyncResult:
        return self._synchronizer.update(report_progress=report_progress, force=force)

    def describe_status(self) -> str:
        return self.get_status(refresh_remote=False).message

