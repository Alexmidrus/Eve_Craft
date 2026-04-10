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
class InstalledSdeVersion:
    """Metadata stored alongside the locally imported SDE catalog."""

    build_number: int
    release_date: datetime
    imported_at: datetime
    archive_url: str | None = None
    archive_etag: str | None = None
    archive_last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class SdeStatus:
    """Snapshot of local availability and remote update status."""

    installed: InstalledSdeVersion | None
    latest: SdeRemoteVersion | None
    update_available: bool
    available: bool
    message: str


@dataclass(frozen=True, slots=True)
class SdeSyncResult:
    """Result of a readiness check or explicit SDE update operation."""

    status: SdeStatus
    updated: bool
    database_path: Path | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
