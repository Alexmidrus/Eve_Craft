from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.platform.sde.application.types_images_synchronizer import TypeImageCollectionSynchronizer
from eve_craft.platform.sde.domain.models import InstalledTypeImageSet, TypeImageRemoteVersion
from eve_craft.platform.sde.infrastructure.types_images_importer import ImportedTypeImageSet


class FakeTypeImageRepository:
    def __init__(
        self,
        installed: InstalledTypeImageSet | None,
        resource_dir: Path,
        has_images: bool,
    ) -> None:
        self._installed = installed
        self._has_images = has_images
        self.resource_dir = resource_dir

    def read_installed_version(self) -> InstalledTypeImageSet | None:
        return self._installed

    def has_any_images(self) -> bool:
        return self._has_images

    def activate_directory(self, imported_directory: Path, version: TypeImageRemoteVersion, image_count: int) -> Path:
        self._installed = InstalledTypeImageSet(
            release_name=version.release_name,
            imported_at=datetime.now(timezone.utc),
            image_count=image_count,
            archive_url=version.archive_url,
            source_url=version.source_url,
            archive_etag=version.etag,
            archive_last_modified=version.last_modified,
            archive_content_length=version.content_length,
        )
        self._has_images = True
        self.resource_dir = imported_directory
        return imported_directory


class FakeTypeImageClient:
    def __init__(self, latest: TypeImageRemoteVersion | None = None, error: Exception | None = None) -> None:
        self._latest = latest
        self._error = error

    def fetch_latest_version(self) -> TypeImageRemoteVersion:
        if self._error is not None:
            raise self._error
        assert self._latest is not None
        return self._latest

    def download_archive(self, version: TypeImageRemoteVersion, destination: Path, report_progress) -> Path:
        destination.write_bytes(b"archive")
        return destination


class FakeTypeImageImporter:
    def import_archive(self, archive_path: Path, version: TypeImageRemoteVersion, report_progress) -> ImportedTypeImageSet:
        target_dir = archive_path.parent / version.release_name.replace(" ", "_")
        target_dir.mkdir(exist_ok=True)
        (target_dir / "34_64.png").write_bytes(b"png")
        return ImportedTypeImageSet(directory=target_dir, image_count=1)


class TypeImageCollectionSynchronizerTests(unittest.TestCase):
    def test_ensure_ready_uses_local_images_if_remote_check_fails(self) -> None:
        installed = InstalledTypeImageSet(
            release_name="Uprising",
            imported_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
            image_count=100,
            archive_url="https://example.invalid/types.zip",
            source_url="https://developers.eveonline.com/docs/services/iec/",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeTypeImageRepository(
                installed=installed,
                resource_dir=Path(temp_dir) / "types",
                has_images=True,
            )
            synchronizer = TypeImageCollectionSynchronizer(
                repository=repository,
                client=FakeTypeImageClient(error=RuntimeError("network error")),
                importer=FakeTypeImageImporter(),
                downloads_dir=Path(temp_dir) / "downloads",
            )

            result = synchronizer.ensure_ready(lambda _progress: None)

            self.assertFalse(result.updated)
            self.assertTrue(result.status.available)
            self.assertIn("Continuing", result.status.message)

    def test_ensure_ready_raises_if_no_local_images_and_remote_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeTypeImageRepository(
                installed=None,
                resource_dir=Path(temp_dir) / "types",
                has_images=False,
            )
            synchronizer = TypeImageCollectionSynchronizer(
                repository=repository,
                client=FakeTypeImageClient(error=RuntimeError("network error")),
                importer=FakeTypeImageImporter(),
                downloads_dir=Path(temp_dir) / "downloads",
            )

            with self.assertRaises(RuntimeError):
                synchronizer.ensure_ready(lambda _progress: None)

    def test_update_installs_images_when_local_set_is_missing(self) -> None:
        latest = TypeImageRemoteVersion(
            release_name="Uprising",
            archive_url="https://example.invalid/types.zip",
            source_url="https://developers.eveonline.com/docs/services/iec/",
            etag="etag-1",
            last_modified="Wed, 15 Mar 2023 13:08:29 GMT",
            content_length=123,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeTypeImageRepository(
                installed=None,
                resource_dir=Path(temp_dir) / "types",
                has_images=False,
            )
            synchronizer = TypeImageCollectionSynchronizer(
                repository=repository,
                client=FakeTypeImageClient(latest=latest),
                importer=FakeTypeImageImporter(),
                downloads_dir=Path(temp_dir) / "downloads",
            )

            result = synchronizer.update(lambda _progress: None, force=False)

            self.assertTrue(result.updated)
            self.assertTrue(result.status.available)
            self.assertEqual("Uprising", result.status.installed.release_name if result.status.installed else None)
            self.assertIsNotNone(result.resource_dir)
