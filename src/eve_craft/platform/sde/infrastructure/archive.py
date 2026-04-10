"""Utilities for parsing SDE archives and JSONL payloads."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from eve_craft.platform.sde.domain.models import SdeRemoteVersion


def iter_jsonl(file_handle) -> Iterator[dict[str, Any]]:
    """Yield parsed JSON objects from a JSONL stream, skipping blank lines."""

    for raw_line in file_handle:
        if not raw_line.strip():
            continue

        yield json.loads(raw_line)


def localized_text(payload: dict[str, Any], key: str, language: str) -> str | None:
    """Resolve a localized text field with English as the fallback language."""

    value = payload.get(key)
    if value is None:
        return None

    if isinstance(value, dict):
        return value.get(language) or value.get("en")

    return str(value)


def localized_name_en(payload: dict[str, Any], key: str = "name") -> str | None:
    """Return the English variant of a localized name field."""

    return localized_text(payload, key, "en")


def localized_name_ru(payload: dict[str, Any], key: str = "name") -> str | None:
    """Return the Russian variant of a localized name field."""

    return localized_text(payload, key, "ru")


def parse_eve_timestamp(value: str) -> datetime:
    """Parse the timestamp format used by the EVE SDE metadata endpoints."""

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_archive_metadata(archive_path: Path) -> tuple[int, datetime]:
    """Read the build number and release date from the archive metadata record."""

    with zipfile.ZipFile(archive_path) as archive:
        with archive.open("_sde.jsonl") as file_handle:
            row = next(iter_jsonl(file_handle))

    return int(row["buildNumber"]), parse_eve_timestamp(row["releaseDate"])


def build_specific_archive_url(build_number: int) -> str:
    """Build the canonical download URL for a specific SDE archive."""

    return (
        "https://developers.eveonline.com/static-data/tranquility/"
        f"eve-online-static-data-{build_number}-jsonl.zip"
    )


def build_remote_version(
    build_number: int,
    release_date: datetime,
    etag: str | None,
    last_modified: str | None,
) -> SdeRemoteVersion:
    """Create a remote-version DTO from metadata returned by the SDE endpoints."""

    metadata_url = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
    return SdeRemoteVersion(
        build_number=build_number,
        release_date=release_date,
        archive_url=build_specific_archive_url(build_number),
        metadata_url=metadata_url,
        etag=etag,
        last_modified=last_modified,
    )

