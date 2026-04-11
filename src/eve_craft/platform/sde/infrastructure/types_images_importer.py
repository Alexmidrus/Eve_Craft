"""Extract the IEC Types image archive into a temporary resource directory."""

from __future__ import annotations

import logging
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from eve_craft.platform.sde.domain.models import TypeImageRemoteVersion
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportedTypeImageSet:
    """Temporary extracted image set ready to be activated."""

    directory: Path
    image_count: int


class TypeImageCollectionImporter:
    """Extract `Types/*.png` assets from the IEC archive into a temporary directory."""

    def __init__(self, temporary_dir: Path) -> None:
        self._temporary_dir = temporary_dir

    def import_archive(
        self,
        archive_path: Path,
        version: TypeImageRemoteVersion,
        report_progress,
    ) -> ImportedTypeImageSet:
        """Extract all type images into a clean temporary directory."""

        self._temporary_dir.mkdir(parents=True, exist_ok=True)
        target_dir = self._temporary_dir / f"types_images_{self._safe_release_name(version.release_name)}"

        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                image_members = self._image_members(archive)
                total_images = len(image_members)
                last_reported_percent: int | None = None

                for index, member in enumerate(image_members, start=1):
                    member_name = Path(member.filename).name
                    with archive.open(member) as source, (target_dir / member_name).open("wb") as destination:
                        shutil.copyfileobj(source, destination)

                    percent = int(index * 100 / total_images)
                    if percent != last_reported_percent:
                        report_progress(
                            OperationProgress(
                                stage="types_images_import",
                                message="Importing IEC Types images",
                                percent=percent,
                                detail=f"Image {index} of {total_images}",
                            )
                        )
                        last_reported_percent = percent

            LOGGER.info("Extracted %s IEC Types images into %s.", total_images, target_dir)
            return ImportedTypeImageSet(directory=target_dir, image_count=total_images)
        except Exception:
            shutil.rmtree(target_dir, ignore_errors=True)
            raise

    @staticmethod
    def _safe_release_name(release_name: str) -> str:
        """Convert the release label into a filesystem-safe temporary directory name."""

        safe = "".join(character if character.isalnum() else "_" for character in release_name).strip("_")
        return safe or "iec_types"

    @staticmethod
    def _image_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        """Return the validated list of type image files contained in the archive."""

        image_members: list[zipfile.ZipInfo] = []

        for member in archive.infolist():
            if member.is_dir():
                continue
            if not member.filename.startswith("Types/"):
                continue

            file_name = Path(member.filename).name
            stem = Path(file_name).stem
            parts = stem.split("_")
            if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in {"32", "64"} or Path(file_name).suffix.lower() != ".png":
                raise RuntimeError(f"Unexpected IEC Types image filename: {member.filename}")

            image_members.append(member)

        if not image_members:
            raise RuntimeError("IEC Types archive does not contain any type images.")

        return image_members
