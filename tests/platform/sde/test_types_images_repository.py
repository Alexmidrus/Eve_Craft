from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eve_craft.platform.sde.domain.models import TypeImageRemoteVersion
from eve_craft.platform.sde.infrastructure.types_images_repository import TypeImageCollectionRepository


class TypeImageCollectionRepositoryTests(unittest.TestCase):
    def test_activate_directory_writes_manifest_and_replaces_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target_dir = root / "resources" / "types"
            repository = TypeImageCollectionRepository(target_dir)

            existing_dir = root / "existing"
            existing_dir.mkdir()
            (existing_dir / "12_64.png").write_bytes(b"old")
            repository.activate_directory(
                imported_directory=existing_dir,
                version=TypeImageRemoteVersion(
                    release_name="Uprising (V21.03 - March 14th 2023)",
                    archive_url="https://example.invalid/Uprising_V21.03_Types.zip",
                    source_url="https://developers.eveonline.com/docs/services/iec/",
                    etag="etag-1",
                    last_modified="Wed, 15 Mar 2023 13:08:29 GMT",
                    content_length=123,
                ),
                image_count=1,
            )

            replacement_dir = root / "replacement"
            replacement_dir.mkdir()
            (replacement_dir / "34_32.png").write_bytes(b"new")
            activated_dir = repository.activate_directory(
                imported_directory=replacement_dir,
                version=TypeImageRemoteVersion(
                    release_name="New Release",
                    archive_url="https://example.invalid/new_types.zip",
                    source_url="https://developers.eveonline.com/docs/services/iec/",
                    etag="etag-2",
                    last_modified="Thu, 16 Mar 2023 13:08:29 GMT",
                    content_length=456,
                ),
                image_count=1,
            )

            self.assertEqual(target_dir, activated_dir)
            self.assertTrue((target_dir / "34_32.png").exists())
            self.assertFalse((target_dir / "12_64.png").exists())

            installed = repository.read_installed_version()
            self.assertIsNotNone(installed)
            assert installed is not None
            self.assertEqual("New Release", installed.release_name)
            self.assertEqual(1, installed.image_count)
            self.assertEqual("etag-2", installed.archive_etag)
            self.assertEqual(456, installed.archive_content_length)
            self.assertTrue(repository.has_any_images())
            self.assertEqual(target_dir / "34_64.png", repository.image_path(34, size=64))

    def test_read_installed_version_returns_none_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "resources" / "types"
            target_dir.mkdir(parents=True)
            (target_dir / "34_32.png").write_bytes(b"png")
            (target_dir / "34_64.png").write_bytes(b"png")

            repository = TypeImageCollectionRepository(target_dir)

            self.assertIsNone(repository.read_installed_version())
            self.assertTrue(repository.has_any_images())

    def test_read_installed_version_returns_none_when_image_count_does_not_match_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target_dir = root / "resources" / "types"
            repository = TypeImageCollectionRepository(target_dir)

            imported_dir = root / "imported"
            imported_dir.mkdir()
            (imported_dir / "34_32.png").write_bytes(b"png")
            (imported_dir / "34_64.png").write_bytes(b"png")
            repository.activate_directory(
                imported_directory=imported_dir,
                version=TypeImageRemoteVersion(
                    release_name="Uprising (V21.03 - March 14th 2023)",
                    archive_url="https://example.invalid/Uprising_V21.03_Types.zip",
                    source_url="https://raw.githubusercontent.com/esi/esi-docs/main/docs/services/iec/index.md",
                    etag="etag-1",
                    last_modified="Wed, 15 Mar 2023 13:08:29 GMT",
                    content_length=123,
                ),
                image_count=2,
            )
            (target_dir / "34_32.png").unlink()

            self.assertIsNone(repository.read_installed_version())
            self.assertTrue(repository.has_any_images())

    def test_has_any_images_uses_fast_path_without_full_count(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target_dir = Path(temp_dir) / "resources" / "types"
            target_dir.mkdir(parents=True)
            (target_dir / "34_32.png").write_bytes(b"png")
            repository = TypeImageCollectionRepository(target_dir)

            with patch.object(repository, "_count_image_files", side_effect=AssertionError("full count was used")):
                self.assertTrue(repository.has_any_images())
