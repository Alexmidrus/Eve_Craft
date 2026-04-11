"""Application workflow for keeping the IEC Types image set current."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from eve_craft.platform.sde.domain.models import (
    InstalledTypeImageSet,
    TypeImageRemoteVersion,
    TypeImageStatus,
    TypeImageSyncResult,
)
from eve_craft.platform.sde.infrastructure.types_images_client import TypeImageCollectionClient
from eve_craft.platform.sde.infrastructure.types_images_importer import TypeImageCollectionImporter
from eve_craft.platform.sde.infrastructure.types_images_repository import TypeImageCollectionRepository
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


class TypeImageCollectionSynchronizer:
    """Coordinate status checks, downloads, extraction, and activation for Types images."""

    def __init__(
        self,
        repository: TypeImageCollectionRepository,
        client: TypeImageCollectionClient,
        importer: TypeImageCollectionImporter,
        downloads_dir: Path,
    ) -> None:
        self._repository = repository
        self._client = client
        self._importer = importer
        self._downloads_dir = downloads_dir

    @property
    def resource_dir(self) -> Path:
        """Expose the active Types image directory for higher-level coordinators."""

        return self._repository.resource_dir

    def get_status(self, refresh_remote: bool) -> TypeImageStatus:
        """Build a status snapshot for the installed and optionally remote image set."""

        installed = self._repository.read_installed_version()
        latest = self._client.fetch_latest_version() if refresh_remote else None
        available = installed is not None
        update_available = not available or bool(latest and not self._is_current(installed, latest))
        message = self._build_status_message(installed, latest, available, update_available)

        return TypeImageStatus(
            installed=installed,
            latest=latest,
            update_available=update_available,
            available=available,
            message=message,
        )

    def ensure_ready(self, report_progress: Callable[[OperationProgress], None]) -> TypeImageSyncResult:
        """Guarantee that the local Types image directory exists and is up to date."""

        installed = self._repository.read_installed_version()
        available = installed is not None
        report_progress(
            OperationProgress(
                stage="types_images_status",
                message="Checking installed Types images",
                percent=5,
                detail=self._describe_installed(installed, available),
            )
        )

        try:
            latest = self._client.fetch_latest_version()
        except Exception as exc:
            if not available:
                raise RuntimeError(
                    "Unable to fetch the IEC Types image archive metadata and no local image set is installed."
                ) from exc

            LOGGER.exception("Unable to fetch IEC Types metadata; continuing with the local image set.")
            warning = "Unable to check the IEC Types image archive. Continuing with the installed local image set."
            return TypeImageSyncResult(
                status=TypeImageStatus(
                    installed=installed,
                    latest=None,
                    update_available=False,
                    available=True,
                    message=warning,
                ),
                updated=False,
                resource_dir=self._repository.resource_dir,
                warnings=(warning,),
            )

        if self._is_current(installed, latest) and available:
            message = f"IEC Types image set '{latest.release_name}' is already up to date."
            report_progress(
                OperationProgress(
                    stage="types_images_ready",
                    message=message,
                    percent=100,
                )
            )
            return TypeImageSyncResult(
                status=TypeImageStatus(
                    installed=installed,
                    latest=latest,
                    update_available=False,
                    available=True,
                    message=message,
                ),
                updated=False,
                resource_dir=self._repository.resource_dir,
            )

        try:
            return self.update(report_progress=report_progress, force=False, latest_override=latest)
        except Exception as exc:
            if not available:
                raise

            LOGGER.exception("Types image update failed; continuing with the installed image set.")
            warning = "Types image update failed. Continuing with the previously installed image set."
            return TypeImageSyncResult(
                status=TypeImageStatus(
                    installed=installed,
                    latest=latest,
                    update_available=True,
                    available=True,
                    message=warning,
                ),
                updated=False,
                resource_dir=self._repository.resource_dir,
                warnings=(warning, str(exc)),
            )

    def update(
        self,
        report_progress: Callable[[OperationProgress], None],
        force: bool,
        latest_override: TypeImageRemoteVersion | None = None,
    ) -> TypeImageSyncResult:
        """Download, extract, and activate the Types image archive when required."""

        installed = self._repository.read_installed_version()
        latest = latest_override or self._client.fetch_latest_version()
        available = installed is not None

        if self._is_current(installed, latest) and available and not force:
            message = f"IEC Types image set '{latest.release_name}' is already up to date."
            return TypeImageSyncResult(
                status=TypeImageStatus(
                    installed=installed,
                    latest=latest,
                    update_available=False,
                    available=True,
                    message=message,
                ),
                updated=False,
                resource_dir=self._repository.resource_dir,
            )

        archive_name = Path(latest.archive_url).name
        archive_path = self._downloads_dir / archive_name
        imported_directory: Path | None = None

        try:
            report_progress(
                OperationProgress(
                    stage="types_images_prepare_download",
                    message=f"Preparing download for IEC Types image set '{latest.release_name}'",
                    percent=5,
                )
            )
            self._downloads_dir.mkdir(parents=True, exist_ok=True)
            self._client.download_archive(
                latest,
                archive_path,
                report_progress=self._range_progress(report_progress, 5, 45),
            )

            imported_set = self._importer.import_archive(
                archive_path=archive_path,
                version=latest,
                report_progress=self._range_progress(report_progress, 45, 95),
            )
            imported_directory = imported_set.directory
            activated_path = self._repository.activate_directory(
                imported_directory=imported_directory,
                version=latest,
                image_count=imported_set.image_count,
            )
            imported_directory = None
            installed = self._repository.read_installed_version()

            report_progress(
                OperationProgress(
                    stage="types_images_cleanup",
                    message="Cleaning temporary image files",
                    percent=98,
                )
            )
            return TypeImageSyncResult(
                status=TypeImageStatus(
                    installed=installed,
                    latest=latest,
                    update_available=False,
                    available=True,
                    message=f"IEC Types image set '{latest.release_name}' is installed.",
                ),
                updated=True,
                resource_dir=activated_path,
            )
        finally:
            if archive_path.exists():
                archive_path.unlink()
            if imported_directory is not None and imported_directory.exists():
                for child in imported_directory.iterdir():
                    if child.is_file():
                        child.unlink()
                imported_directory.rmdir()

    def _range_progress(
        self,
        report_progress: Callable[[OperationProgress], None],
        start_percent: int,
        end_percent: int,
    ) -> Callable[[OperationProgress], None]:
        """Map child progress events into a dedicated range of the parent operation."""

        def adapter(progress: OperationProgress) -> None:
            percent = progress.clamp_percent()
            mapped = None
            if percent is not None:
                mapped = start_percent + int((end_percent - start_percent) * percent / 100)

            report_progress(
                OperationProgress(
                    stage=progress.stage,
                    message=progress.message,
                    percent=mapped,
                    detail=progress.detail,
                    indeterminate=progress.indeterminate and mapped is None,
                )
            )

        return adapter

    @staticmethod
    def _is_current(
        installed: InstalledTypeImageSet | None,
        latest: TypeImageRemoteVersion,
    ) -> bool:
        """Return whether the installed image set matches the current remote archive."""

        if installed is None:
            return False
        if installed.archive_url != latest.archive_url:
            return False
        if installed.archive_etag and latest.etag and installed.archive_etag != latest.etag:
            return False
        if installed.archive_last_modified and latest.last_modified and installed.archive_last_modified != latest.last_modified:
            return False
        if (
            installed.archive_content_length is not None
            and latest.content_length is not None
            and installed.archive_content_length != latest.content_length
        ):
            return False

        return True

    @staticmethod
    def _build_status_message(
        installed: InstalledTypeImageSet | None,
        latest: TypeImageRemoteVersion | None,
        available: bool,
        update_available: bool,
    ) -> str:
        """Translate the image-set state into a UI-friendly status message."""

        if not available and latest is None:
            return "IEC Types image set is not installed."
        if not available and latest is not None:
            return f"IEC Types image set is not installed. Current release is '{latest.release_name}'."
        if installed is not None and latest is None:
            return f"Installed IEC Types image set: '{installed.release_name}'."
        if installed is not None and latest is not None and update_available:
            return f"Installed IEC Types image set '{installed.release_name}'. Current release '{latest.release_name}' is available."
        return f"IEC Types image set '{installed.release_name if installed is not None else latest.release_name}' is up to date."

    @staticmethod
    def _describe_installed(installed: InstalledTypeImageSet | None, available: bool) -> str:
        """Describe the currently installed image set for progress reporting."""

        if installed is None or not available:
            return "No local IEC Types image set was found."

        return f"Installed release '{installed.release_name}' with {installed.image_count} images."
