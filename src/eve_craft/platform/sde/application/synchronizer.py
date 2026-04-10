"""Application workflow that keeps the local SDE database current."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from eve_craft.platform.sde.domain.models import InstalledSdeVersion, SdeStatus, SdeSyncResult
from eve_craft.platform.sde.infrastructure.archive import read_archive_metadata
from eve_craft.platform.sde.infrastructure.client import EveStaticDataClient
from eve_craft.platform.sde.infrastructure.importer import SdeImporter
from eve_craft.platform.sde.infrastructure.repository import SdeMetadataRepository
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


class SdeSynchronizer:
    """Coordinate local SDE status checks, downloads, imports, and activation."""

    def __init__(
        self,
        repository: SdeMetadataRepository,
        client: EveStaticDataClient,
        importer: SdeImporter,
        downloads_dir: Path,
    ) -> None:
        self._repository = repository
        self._client = client
        self._importer = importer
        self._downloads_dir = downloads_dir

    def get_status(self, refresh_remote: bool) -> SdeStatus:
        """Build a status snapshot from the installed build and optional remote metadata."""

        installed = self._repository.read_installed_version()
        latest = self._client.fetch_latest_version() if refresh_remote else None
        update_available = bool(installed and latest and latest.build_number > installed.build_number)
        message = self._build_status_message(installed, latest, update_available)

        return SdeStatus(
            installed=installed,
            latest=latest,
            update_available=update_available,
            available=installed is not None,
            message=message,
        )

    def ensure_ready(self, report_progress: Callable[[OperationProgress], None]) -> SdeSyncResult:
        """Guarantee a usable local catalog or fail fast when none can be prepared."""

        installed = self._repository.read_installed_version()
        report_progress(
            OperationProgress(
                stage="sde_status",
                message="Checking installed SDE",
                percent=5,
                detail=self._describe_installed(installed),
            )
        )

        try:
            latest = self._client.fetch_latest_version()
        except Exception as exc:
            if installed is None:
                raise RuntimeError("Unable to fetch the latest SDE version and no local SDE is installed.") from exc

            # Startup may continue with the previously activated catalog when the network is unavailable.
            LOGGER.exception("Unable to fetch remote SDE metadata; continuing with the local build.")
            warning = "Unable to check the latest SDE version. Continuing with the installed local build."
            return SdeSyncResult(
                status=SdeStatus(
                    installed=installed,
                    latest=None,
                    update_available=False,
                    available=True,
                    message=warning,
                ),
                updated=False,
                database_path=self._repository.database_path if self._repository.database_path.exists() else None,
                warnings=(warning,),
            )

        if installed is not None and installed.build_number >= latest.build_number:
            message = f"SDE build {installed.build_number} is already up to date."
            report_progress(
                OperationProgress(
                    stage="sde_ready",
                    message=message,
                    percent=100,
                )
            )
            return SdeSyncResult(
                status=SdeStatus(
                    installed=installed,
                    latest=latest,
                    update_available=False,
                    available=True,
                    message=message,
                ),
                updated=False,
                database_path=self._repository.database_path,
            )

        try:
            return self.update(report_progress=report_progress, force=False, latest_override=latest)
        except Exception as exc:
            if installed is None:
                raise

            # A failed refresh should not brick the app if an older catalog is still usable.
            LOGGER.exception("SDE update failed; continuing with the installed build.")
            warning = "SDE update failed. Continuing with the previously installed build."
            return SdeSyncResult(
                status=SdeStatus(
                    installed=installed,
                    latest=latest,
                    update_available=True,
                    available=True,
                    message=warning,
                ),
                updated=False,
                database_path=self._repository.database_path,
                warnings=(warning, str(exc)),
            )

    def update(
        self,
        report_progress: Callable[[OperationProgress], None],
        force: bool,
        latest_override=None,
    ) -> SdeSyncResult:
        """Download, import, and activate the target SDE build."""

        installed = self._repository.read_installed_version()
        latest = latest_override or self._client.fetch_latest_version()

        if installed is not None and installed.build_number >= latest.build_number and not force:
            message = f"SDE build {installed.build_number} is already up to date."
            return SdeSyncResult(
                status=SdeStatus(
                    installed=installed,
                    latest=latest,
                    update_available=False,
                    available=True,
                    message=message,
                ),
                updated=False,
                database_path=self._repository.database_path,
            )

        archive_path = self._downloads_dir / f"sde_{latest.build_number}.zip"
        temp_database_path: Path | None = None

        try:
            report_progress(
                OperationProgress(
                    stage="sde_prepare_download",
                    message=f"Preparing download for SDE build {latest.build_number}",
                    percent=5,
                )
            )
            self._downloads_dir.mkdir(parents=True, exist_ok=True)
            self._client.download_archive(
                latest,
                archive_path,
                report_progress=self._range_progress(report_progress, 5, 40),
            )

            archive_build, _archive_release_date = read_archive_metadata(archive_path)
            if archive_build != latest.build_number:
                raise RuntimeError(
                    f"Downloaded archive build {archive_build} does not match the expected build {latest.build_number}."
                )

            # Import into a temporary database first so the active catalog is replaced only after success.
            temp_database_path = self._importer.import_archive(
                archive_path=archive_path,
                version=latest,
                report_progress=self._range_progress(report_progress, 40, 95),
            )
            activated_path = self._repository.activate_database(temp_database_path)
            temp_database_path = None

            installed = self._repository.read_installed_version()
            status = SdeStatus(
                installed=installed,
                latest=latest,
                update_available=False,
                available=True,
                message=f"SDE build {latest.build_number} is installed.",
            )
            report_progress(
                OperationProgress(
                    stage="sde_cleanup",
                    message="Cleaning temporary files",
                    percent=98,
                )
            )
            return SdeSyncResult(
                status=status,
                updated=True,
                database_path=activated_path,
            )
        finally:
            # Both the archive and temporary database are disposable build artifacts.
            if archive_path.exists():
                archive_path.unlink()
            if temp_database_path is not None and temp_database_path.exists():
                temp_database_path.unlink()

    def _range_progress(
        self,
        report_progress: Callable[[OperationProgress], None],
        start_percent: int,
        end_percent: int,
    ) -> Callable[[OperationProgress], None]:
        """Map child task progress into a dedicated range of the parent operation."""

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
    def _build_status_message(
        installed: InstalledSdeVersion | None,
        latest,
        update_available: bool,
    ) -> str:
        """Translate synchronization state into a UI-friendly status message."""

        if installed is None and latest is None:
            return "SDE is not installed."
        if installed is None and latest is not None:
            return f"SDE is not installed. Latest build is {latest.build_number}."
        if installed is not None and latest is None:
            return f"Installed SDE build: {installed.build_number}."
        if update_available:
            return f"Installed build {installed.build_number}. Latest build {latest.build_number} is available."
        return f"SDE build {installed.build_number} is up to date."

    @staticmethod
    def _describe_installed(installed: InstalledSdeVersion | None) -> str:
        """Describe the currently activated local build for progress reporting."""

        if installed is None:
            return "No local SDE database was found."

        return f"Installed build {installed.build_number}"

