"""Facade for the SDE subsystem used by the rest of the application."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from eve_craft.app.config import AppConfig
from eve_craft.platform.sde.application.resource_synchronizer import SdeResourceSynchronizer
from eve_craft.platform.sde.application.synchronizer import SdeSynchronizer
from eve_craft.platform.sde.domain.models import SdeStatus, SdeSyncResult
from eve_craft.platform.sde.infrastructure.client import EveStaticDataClient
from eve_craft.platform.sde.infrastructure.importer import SdeImporter
from eve_craft.platform.sde.infrastructure.repository import SdeMetadataRepository
from eve_craft.platform.sde.infrastructure.types_images_client import TypeImageCollectionClient
from eve_craft.platform.sde.infrastructure.types_images_importer import TypeImageCollectionImporter
from eve_craft.platform.sde.infrastructure.types_images_repository import TypeImageCollectionRepository
from eve_craft.platform.sde.application.types_images_synchronizer import TypeImageCollectionSynchronizer
from eve_craft.shared.progress import OperationProgress


class SdeService:
    """Expose a narrow application-facing API for SDE state and synchronization."""

    def __init__(self, config: AppConfig) -> None:
        self._database_repository = SdeMetadataRepository(config.paths.sde_database_path)
        database_synchronizer = SdeSynchronizer(
            repository=self._database_repository,
            client=EveStaticDataClient(),
            importer=SdeImporter(config.paths.temporary_dir),
            downloads_dir=config.paths.downloads_dir,
        )
        self._type_images_repository = TypeImageCollectionRepository(config.paths.types_images_dir)
        type_images_synchronizer = TypeImageCollectionSynchronizer(
            repository=self._type_images_repository,
            client=TypeImageCollectionClient(),
            importer=TypeImageCollectionImporter(config.paths.temporary_dir),
            downloads_dir=config.paths.downloads_dir,
        )
        self._synchronizer = SdeResourceSynchronizer(
            database_synchronizer=database_synchronizer,
            type_images_synchronizer=type_images_synchronizer,
        )

    @property
    def database_path(self) -> Path:
        """Return the active SQLite database path used as the SDE catalog."""

        return self._database_repository.database_path

    @property
    def types_images_dir(self) -> Path:
        """Return the resource directory that stores installed type images."""

        return self._type_images_repository.resource_dir

    def get_status(self, refresh_remote: bool = False) -> SdeStatus:
        """Return the current SDE status, optionally refreshing remote metadata."""

        return self._synchronizer.get_status(refresh_remote=refresh_remote)

    def ensure_ready(self, report_progress: Callable[[OperationProgress], None]) -> SdeSyncResult:
        """Ensure that a usable local SDE database exists before startup continues."""

        return self._synchronizer.ensure_ready(report_progress=report_progress)

    def update(self, report_progress: Callable[[OperationProgress], None], force: bool = False) -> SdeSyncResult:
        """Download and install the latest SDE build when needed."""

        return self._synchronizer.update(report_progress=report_progress, force=force)

    def describe_status(self) -> str:
        """Return a cached human-readable status summary for the UI."""

        return self.get_status(refresh_remote=False).message

    def type_image_path(self, type_id: int, size: int = 64) -> Path:
        """Build the expected path of a locally installed type image."""

        return self._type_images_repository.image_path(type_id=type_id, size=size)

