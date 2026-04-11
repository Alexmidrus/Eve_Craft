"""Coordinate database and image synchronization for the full SDE resource set."""

from __future__ import annotations

from collections.abc import Callable

from eve_craft.platform.sde.application.synchronizer import SdeSynchronizer
from eve_craft.platform.sde.application.types_images_synchronizer import TypeImageCollectionSynchronizer
from eve_craft.platform.sde.domain.models import SdeStatus, SdeSyncResult, TypeImageStatus, TypeImageSyncResult
from eve_craft.shared.progress import OperationProgress


class SdeResourceSynchronizer:
    """Synchronize the SDE database and the IEC Types image pack as one resource bundle."""

    def __init__(
        self,
        database_synchronizer: SdeSynchronizer,
        type_images_synchronizer: TypeImageCollectionSynchronizer,
    ) -> None:
        self._database_synchronizer = database_synchronizer
        self._type_images_synchronizer = type_images_synchronizer

    def get_status(self, refresh_remote: bool) -> SdeStatus:
        """Return the combined status of the database and Types image resources."""

        database_status = self._database_synchronizer.get_status(refresh_remote=refresh_remote)
        type_images_status = self._type_images_synchronizer.get_status(refresh_remote=refresh_remote)
        return self._combine_statuses(database_status, type_images_status)

    def ensure_ready(self, report_progress: Callable[[OperationProgress], None]) -> SdeSyncResult:
        """Ensure that the missing parts of the SDE resource bundle are locally available."""

        database_status = self._database_synchronizer.get_status(refresh_remote=False)
        type_images_status = self._type_images_synchronizer.get_status(refresh_remote=False)

        if database_status.available:
            report_progress(
                OperationProgress(
                    stage="sde_ready",
                    message=database_status.message,
                    percent=70,
                )
            )
            database_result = self._existing_database_result(database_status)
        else:
            database_result = self._database_synchronizer.ensure_ready(
                report_progress=self._range_progress(report_progress, 0, 70)
            )

        if type_images_status.available:
            report_progress(
                OperationProgress(
                    stage="types_images_ready",
                    message=type_images_status.message,
                    percent=100,
                )
            )
            type_images_result = self._existing_type_images_result(type_images_status)
        else:
            type_images_result = self._type_images_synchronizer.ensure_ready(
                report_progress=self._range_progress(report_progress, 70, 100)
            )

        status = self._combine_statuses(database_result.status, type_images_result.status)
        return SdeSyncResult(
            status=status,
            updated=database_result.updated or type_images_result.updated,
            database_path=database_result.database_path,
            warnings=database_result.warnings + type_images_result.warnings,
            type_images=type_images_result,
        )

    def _existing_database_result(self, status: SdeStatus) -> SdeSyncResult:
        """Build a no-op result for an already available local SDE database."""

        database_path = getattr(self._database_synchronizer, "database_path", None)
        return SdeSyncResult(
            status=status,
            updated=False,
            database_path=database_path if status.available else None,
        )

    def _existing_type_images_result(self, status: TypeImageStatus) -> TypeImageSyncResult:
        """Build a no-op result for an already available local Types image set."""

        resource_dir = getattr(self._type_images_synchronizer, "resource_dir", None)
        return TypeImageSyncResult(
            status=status,
            updated=False,
            resource_dir=resource_dir if status.available else None,
        )

    def update(self, report_progress: Callable[[OperationProgress], None], force: bool = False) -> SdeSyncResult:
        """Update the database and the Types image set using one progress stream."""

        database_result = self._database_synchronizer.update(
            report_progress=self._range_progress(report_progress, 0, 70),
            force=force,
        )
        type_images_result = self._type_images_synchronizer.update(
            report_progress=self._range_progress(report_progress, 70, 100),
            force=force,
        )

        status = self._combine_statuses(database_result.status, type_images_result.status)
        return SdeSyncResult(
            status=status,
            updated=database_result.updated or type_images_result.updated,
            database_path=database_result.database_path,
            warnings=database_result.warnings + type_images_result.warnings,
            type_images=type_images_result,
        )

    @staticmethod
    def _combine_statuses(database_status: SdeStatus, type_images_status: TypeImageStatus) -> SdeStatus:
        """Merge database and image-set status into the single status model exposed to the UI."""

        messages = [database_status.message, type_images_status.message]
        combined_message = " ".join(message for index, message in enumerate(messages) if message and message not in messages[:index])

        return SdeStatus(
            installed=database_status.installed,
            latest=database_status.latest,
            update_available=database_status.update_available or type_images_status.update_available,
            available=database_status.available and type_images_status.available,
            message=combined_message,
            type_images=type_images_status,
        )

    @staticmethod
    def _range_progress(
        report_progress: Callable[[OperationProgress], None],
        start_percent: int,
        end_percent: int,
    ) -> Callable[[OperationProgress], None]:
        """Map a child synchronizer progress stream into a parent progress range."""

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
