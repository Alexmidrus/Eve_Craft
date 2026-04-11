from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.platform.sde.application.resource_synchronizer import SdeResourceSynchronizer
from eve_craft.platform.sde.domain.models import (
    InstalledSdeVersion,
    InstalledTypeImageSet,
    SdeStatus,
    SdeSyncResult,
    TypeImageStatus,
    TypeImageSyncResult,
)


class FakeDatabaseSynchronizer:
    def __init__(self, status: SdeStatus, result: SdeSyncResult) -> None:
        self._status = status
        self._result = result
        self.database_path = result.database_path
        self.ensure_ready_calls = 0

    def get_status(self, refresh_remote: bool) -> SdeStatus:
        return self._status

    def ensure_ready(self, report_progress) -> SdeSyncResult:
        self.ensure_ready_calls += 1
        return self._result

    def update(self, report_progress, force: bool) -> SdeSyncResult:
        return self._result


class FakeTypeImageSynchronizer:
    def __init__(self, status: TypeImageStatus, result: TypeImageSyncResult) -> None:
        self._status = status
        self._result = result
        self.resource_dir = result.resource_dir
        self.ensure_ready_calls = 0

    def get_status(self, refresh_remote: bool) -> TypeImageStatus:
        return self._status

    def ensure_ready(self, report_progress) -> TypeImageSyncResult:
        self.ensure_ready_calls += 1
        return self._result

    def update(self, report_progress, force: bool) -> TypeImageSyncResult:
        return self._result


class SdeResourceSynchronizerTests(unittest.TestCase):
    @staticmethod
    def _installed_database_status(message: str) -> SdeStatus:
        return SdeStatus(
            installed=InstalledSdeVersion(
                build_number=111,
                release_date=datetime(2026, 4, 10, tzinfo=timezone.utc),
                imported_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
            ),
            latest=None,
            update_available=False,
            available=True,
            message=message,
        )

    @staticmethod
    def _installed_image_status(message: str) -> TypeImageStatus:
        return TypeImageStatus(
            installed=InstalledTypeImageSet(
                release_name="Uprising",
                imported_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
                image_count=2,
                archive_url="https://example.invalid/types.zip",
                source_url="https://example.invalid/iec/index.md",
            ),
            latest=None,
            update_available=False,
            available=True,
            message=message,
        )

    def test_ensure_ready_combines_database_and_type_images_results_when_both_are_missing(self) -> None:
        database_synchronizer = FakeDatabaseSynchronizer(
            status=SdeStatus(
                installed=None,
                latest=None,
                update_available=False,
                available=False,
                message="SDE is not installed.",
            ),
            result=SdeSyncResult(
                status=self._installed_database_status("SDE build 111 is installed."),
                updated=True,
                database_path=Path("sde.sqlite3"),
                warnings=("db warning",),
            ),
        )
        type_images_synchronizer = FakeTypeImageSynchronizer(
            status=TypeImageStatus(
                installed=None,
                latest=None,
                update_available=False,
                available=False,
                message="IEC Types image set is not installed.",
            ),
            result=TypeImageSyncResult(
                status=self._installed_image_status("IEC Types image set 'Uprising' is installed."),
                updated=True,
                resource_dir=Path("types"),
                warnings=("image warning",),
            ),
        )

        synchronizer = SdeResourceSynchronizer(
            database_synchronizer=database_synchronizer,
            type_images_synchronizer=type_images_synchronizer,
        )

        result = synchronizer.ensure_ready(lambda _progress: None)

        self.assertEqual(1, database_synchronizer.ensure_ready_calls)
        self.assertEqual(1, type_images_synchronizer.ensure_ready_calls)
        self.assertTrue(result.updated)
        self.assertTrue(result.status.available)
        self.assertTrue(result.status.type_images.available)
        self.assertEqual(("db warning", "image warning"), result.warnings)
        self.assertIsNotNone(result.type_images)
        assert result.type_images is not None
        self.assertEqual(Path("types"), result.type_images.resource_dir)
        self.assertIn("SDE build 111 is installed.", result.status.message)
        self.assertIn("IEC Types image set 'Uprising' is installed.", result.status.message)

    def test_ensure_ready_only_rebuilds_database_when_images_already_exist(self) -> None:
        available_image_status = self._installed_image_status("IEC Types image set 'Uprising' is already available.")
        database_synchronizer = FakeDatabaseSynchronizer(
            status=SdeStatus(
                installed=None,
                latest=None,
                update_available=False,
                available=False,
                message="SDE is not installed.",
            ),
            result=SdeSyncResult(
                status=self._installed_database_status("SDE build 111 is installed."),
                updated=True,
                database_path=Path("sde.sqlite3"),
                warnings=("db warning",),
            ),
        )
        type_images_synchronizer = FakeTypeImageSynchronizer(
            status=available_image_status,
            result=TypeImageSyncResult(
                status=available_image_status,
                updated=True,
                resource_dir=Path("types"),
                warnings=("image warning",),
            ),
        )
        synchronizer = SdeResourceSynchronizer(
            database_synchronizer=database_synchronizer,
            type_images_synchronizer=type_images_synchronizer,
        )

        result = synchronizer.ensure_ready(lambda _progress: None)

        self.assertEqual(1, database_synchronizer.ensure_ready_calls)
        self.assertEqual(0, type_images_synchronizer.ensure_ready_calls)
        self.assertTrue(result.updated)
        self.assertEqual(("db warning",), result.warnings)
        self.assertEqual(Path("sde.sqlite3"), result.database_path)
        self.assertIsNotNone(result.type_images)
        assert result.type_images is not None
        self.assertFalse(result.type_images.updated)
        self.assertEqual(Path("types"), result.type_images.resource_dir)
        self.assertIn("IEC Types image set 'Uprising' is already available.", result.status.message)

    def test_ensure_ready_only_rebuilds_images_when_database_already_exists(self) -> None:
        available_database_status = self._installed_database_status("SDE build 111 is already available.")
        type_images_synchronizer = FakeTypeImageSynchronizer(
            status=TypeImageStatus(
                installed=None,
                latest=None,
                update_available=False,
                available=False,
                message="IEC Types image set is not installed.",
            ),
            result=TypeImageSyncResult(
                status=self._installed_image_status("IEC Types image set 'Uprising' is installed."),
                updated=True,
                resource_dir=Path("types"),
                warnings=("image warning",),
            ),
        )
        database_synchronizer = FakeDatabaseSynchronizer(
            status=available_database_status,
            result=SdeSyncResult(
                status=available_database_status,
                updated=True,
                database_path=Path("sde.sqlite3"),
                warnings=("db warning",),
            ),
        )
        synchronizer = SdeResourceSynchronizer(
            database_synchronizer=database_synchronizer,
            type_images_synchronizer=type_images_synchronizer,
        )

        result = synchronizer.ensure_ready(lambda _progress: None)

        self.assertEqual(0, database_synchronizer.ensure_ready_calls)
        self.assertEqual(1, type_images_synchronizer.ensure_ready_calls)
        self.assertTrue(result.updated)
        self.assertEqual(("image warning",), result.warnings)
        self.assertEqual(Path("sde.sqlite3"), result.database_path)
        self.assertIsNotNone(result.type_images)
        assert result.type_images is not None
        self.assertTrue(result.type_images.updated)
        self.assertEqual(Path("types"), result.type_images.resource_dir)
        self.assertIn("SDE build 111 is already available.", result.status.message)

    def test_ensure_ready_skips_downloads_when_everything_is_already_available(self) -> None:
        available_database_status = self._installed_database_status("SDE build 111 is already available.")
        available_image_status = self._installed_image_status("IEC Types image set 'Uprising' is already available.")
        database_synchronizer = FakeDatabaseSynchronizer(
            status=available_database_status,
            result=SdeSyncResult(
                status=available_database_status,
                updated=True,
                database_path=Path("sde.sqlite3"),
                warnings=("db warning",),
            ),
        )
        type_images_synchronizer = FakeTypeImageSynchronizer(
            status=available_image_status,
            result=TypeImageSyncResult(
                status=available_image_status,
                updated=True,
                resource_dir=Path("types"),
                warnings=("image warning",),
            ),
        )
        synchronizer = SdeResourceSynchronizer(
            database_synchronizer=database_synchronizer,
            type_images_synchronizer=type_images_synchronizer,
        )

        result = synchronizer.ensure_ready(lambda _progress: None)

        self.assertEqual(0, database_synchronizer.ensure_ready_calls)
        self.assertEqual(0, type_images_synchronizer.ensure_ready_calls)
        self.assertFalse(result.updated)
        self.assertEqual((), result.warnings)
        self.assertEqual(Path("sde.sqlite3"), result.database_path)
        self.assertIsNotNone(result.type_images)
        assert result.type_images is not None
        self.assertFalse(result.type_images.updated)
        self.assertEqual(Path("types"), result.type_images.resource_dir)
        self.assertTrue(result.status.available)
