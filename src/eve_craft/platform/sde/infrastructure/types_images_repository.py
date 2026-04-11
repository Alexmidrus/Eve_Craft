"""Persistence helpers for the locally installed IEC Types image set."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from eve_craft.platform.sde.domain.models import InstalledTypeImageSet, TypeImageRemoteVersion

LOGGER = logging.getLogger(__name__)


class TypeImageCollectionRepository:
    """Read and activate the local IEC Types image resource directory."""

    MANIFEST_FILENAME = "manifest.json"
    _IMAGE_SUFFIXES = ("_32.png", "_64.png")

    def __init__(self, resource_dir: Path) -> None:
        self._resource_dir = resource_dir

    @property
    def resource_dir(self) -> Path:
        """Return the active resource directory that stores imported type images."""

        return self._resource_dir

    def read_installed_version(self) -> InstalledTypeImageSet | None:
        """Read the manifest describing the currently activated image set."""

        manifest_path = self._resource_dir / self.MANIFEST_FILENAME
        if not manifest_path.exists():
            return None

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            LOGGER.exception("Unable to read installed IEC Types manifest from %s.", manifest_path)
            return None

        installed = InstalledTypeImageSet(
            release_name=str(payload["release_name"]),
            imported_at=datetime.fromisoformat(str(payload["imported_at"])),
            image_count=int(payload["image_count"]),
            archive_url=str(payload["archive_url"]),
            source_url=str(payload["source_url"]),
            archive_etag=payload.get("archive_etag"),
            archive_last_modified=payload.get("archive_last_modified"),
            archive_content_length=payload.get("archive_content_length"),
        )
        actual_image_count = self._count_image_files()
        if actual_image_count != installed.image_count:
            LOGGER.warning(
                "Installed IEC Types image set is incomplete in %s: expected %s files from manifest, found %s.",
                self._resource_dir,
                installed.image_count,
                actual_image_count,
            )
            return None

        return installed

    def activate_directory(
        self,
        imported_directory: Path,
        version: TypeImageRemoteVersion,
        image_count: int,
    ) -> Path:
        """Replace the active resource directory with a freshly imported image set."""

        self._resource_dir.parent.mkdir(parents=True, exist_ok=True)
        backup_directory = self._resource_dir.with_name(f"{self._resource_dir.name}.backup")

        self._write_manifest(imported_directory, version, image_count)

        if backup_directory.exists():
            shutil.rmtree(backup_directory)

        if self._resource_dir.exists():
            os.replace(self._resource_dir, backup_directory)

        try:
            os.replace(imported_directory, self._resource_dir)
        except Exception:
            if backup_directory.exists() and not self._resource_dir.exists():
                os.replace(backup_directory, self._resource_dir)
            raise
        finally:
            if backup_directory.exists():
                shutil.rmtree(backup_directory, ignore_errors=True)

        LOGGER.info("Activated IEC Types image directory %s.", self._resource_dir)
        return self._resource_dir

    def image_path(self, type_id: int, size: int = 64) -> Path:
        """Build the expected path for a type image in the active resource directory."""

        if size not in {32, 64}:
            raise ValueError("Type images are only available in 32px and 64px sizes.")

        return self._resource_dir / f"{type_id}_{size}.png"

    def has_any_images(self) -> bool:
        """Return whether the resource directory contains at least one type image."""

        return next(self._iter_image_files(), None) is not None

    def _count_image_files(self) -> int:
        """Count the imported type images currently present in the resource directory."""

        return sum(1 for _path in self._iter_image_files())

    def _iter_image_files(self):
        """Yield image files stored in the active resource directory."""

        if not self._resource_dir.exists():
            return

        for path in self._resource_dir.iterdir():
            if path.is_file() and path.name.endswith(self._IMAGE_SUFFIXES):
                yield path

    def _write_manifest(
        self,
        target_directory: Path,
        version: TypeImageRemoteVersion,
        image_count: int,
    ) -> None:
        """Write the manifest used to determine the installed image set version."""

        manifest_path = target_directory / self.MANIFEST_FILENAME
        payload = {
            "release_name": version.release_name,
            "archive_url": version.archive_url,
            "source_url": version.source_url,
            "archive_etag": version.etag,
            "archive_last_modified": version.last_modified,
            "archive_content_length": version.content_length,
            "image_count": image_count,
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
