from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from eve_craft.platform.sde.domain.models import TypeImageRemoteVersion
from eve_craft.platform.sde.infrastructure.types_images_importer import TypeImageCollectionImporter


def build_sample_types_archive(target_path: Path, invalid_name: str | None = None) -> None:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("Types/34_32.png", b"png32")
        archive.writestr("Types/34_64.png", b"png64")
        archive.writestr("Types/35_64.png", b"png64b")
        archive.writestr("README.txt", b"ignored")

        if invalid_name is not None:
            archive.writestr(f"Types/{invalid_name}", b"broken")


class TypeImageCollectionImporterTests(unittest.TestCase):
    def test_import_archive_extracts_type_images_into_flat_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "types.zip"
            build_sample_types_archive(archive_path)

            importer = TypeImageCollectionImporter(temp_path / "tmp")
            imported = importer.import_archive(
                archive_path=archive_path,
                version=TypeImageRemoteVersion(
                    release_name="Uprising",
                    archive_url="https://example.invalid/types.zip",
                    source_url="https://developers.eveonline.com/docs/services/iec/",
                ),
                report_progress=lambda _progress: None,
            )

            self.assertEqual(3, imported.image_count)
            self.assertTrue((imported.directory / "34_32.png").exists())
            self.assertTrue((imported.directory / "34_64.png").exists())
            self.assertTrue((imported.directory / "35_64.png").exists())
            self.assertFalse((imported.directory / "Types").exists())

    def test_import_archive_rejects_unexpected_types_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / "types_invalid.zip"
            build_sample_types_archive(archive_path, invalid_name="not_a_type.png")

            importer = TypeImageCollectionImporter(temp_path / "tmp")

            with self.assertRaises(RuntimeError):
                importer.import_archive(
                    archive_path=archive_path,
                    version=TypeImageRemoteVersion(
                        release_name="Uprising",
                        archive_url="https://example.invalid/types.zip",
                        source_url="https://developers.eveonline.com/docs/services/iec/",
                    ),
                    report_progress=lambda _progress: None,
                )
