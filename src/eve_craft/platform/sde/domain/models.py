from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SdeRemoteVersion:
    """Metadata about the latest SDE build published by CCP."""

    build_number: int
    release_date: datetime
    archive_url: str
    metadata_url: str
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class TypeImageRemoteVersion:
    """Metadata about the current IEC Types image archive published by CCP."""

    release_name: str
    archive_url: str
    source_url: str
    etag: str | None = None
    last_modified: str | None = None
    content_length: int | None = None


@dataclass(frozen=True, slots=True)
class InstalledSdeVersion:
    """Metadata stored alongside the locally imported SDE catalog."""

    build_number: int
    release_date: datetime
    imported_at: datetime
    archive_url: str | None = None
    archive_etag: str | None = None
    archive_last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class InstalledTypeImageSet:
    """Metadata describing the locally installed IEC Types image set."""

    release_name: str
    imported_at: datetime
    image_count: int
    archive_url: str
    source_url: str
    archive_etag: str | None = None
    archive_last_modified: str | None = None
    archive_content_length: int | None = None


@dataclass(frozen=True, slots=True)
class TypeImageStatus:
    """Snapshot of local availability and remote update status for Types images."""

    installed: InstalledTypeImageSet | None = None
    latest: TypeImageRemoteVersion | None = None
    update_available: bool = False
    available: bool = False
    message: str = "Types image set status is not available."


@dataclass(frozen=True, slots=True)
class SdeStatus:
    """Snapshot of local availability and remote update status."""

    installed: InstalledSdeVersion | None
    latest: SdeRemoteVersion | None
    update_available: bool
    available: bool
    message: str
    type_images: TypeImageStatus = field(default_factory=TypeImageStatus)


@dataclass(frozen=True, slots=True)
class TypeImageSyncResult:
    """Result of a readiness check or update operation for Types images."""

    status: TypeImageStatus
    updated: bool
    resource_dir: Path | None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SdeSyncResult:
    """Result of a readiness check or explicit SDE update operation."""

    status: SdeStatus
    updated: bool
    database_path: Path | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    type_images: TypeImageSyncResult | None = None
