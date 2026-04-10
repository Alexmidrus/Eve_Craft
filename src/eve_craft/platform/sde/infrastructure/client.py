from __future__ import annotations

import json
import logging
import urllib.request
from pathlib import Path

from eve_craft.platform.sde.domain.models import SdeRemoteVersion
from eve_craft.platform.sde.infrastructure.archive import build_remote_version, parse_eve_timestamp
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


class EveStaticDataClient:
    _UNKNOWN_SIZE_REPORT_STEP = 1024 * 1024 * 5

    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch_latest_version(self) -> SdeRemoteVersion:
        metadata_url = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
        request = urllib.request.Request(metadata_url, headers=self._headers())
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            row = json.loads(response.read().decode("utf-8"))

        build_number = int(row["buildNumber"])
        release_date = parse_eve_timestamp(row["releaseDate"])
        etag, last_modified = self._head_archive(build_number)
        version = build_remote_version(
            build_number=build_number,
            release_date=release_date,
            etag=etag,
            last_modified=last_modified,
        )
        LOGGER.info("Resolved latest SDE build %s.", version.build_number)
        return version

    def download_archive(
        self,
        version: SdeRemoteVersion,
        destination: Path,
        report_progress,
    ) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(version.archive_url, headers=self._headers())

        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            total_size = self._parse_content_length(response.headers.get("Content-Length"))
            downloaded = 0
            last_reported_percent: int | None = None
            last_reported_bytes = 0

            with destination.open("wb") as archive_file:
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break

                    archive_file.write(chunk)
                    downloaded += len(chunk)

                    percent = None
                    if total_size is not None and total_size > 0:
                        percent = int(downloaded * 100 / total_size)

                    if self._should_report_download_progress(
                        downloaded=downloaded,
                        total_size=total_size,
                        percent=percent,
                        last_reported_percent=last_reported_percent,
                        last_reported_bytes=last_reported_bytes,
                    ):
                        report_progress(
                            OperationProgress(
                                stage="sde_download",
                                message=f"Downloading SDE build {version.build_number}",
                                percent=percent,
                                detail=f"{downloaded} bytes downloaded",
                                indeterminate=percent is None,
                            )
                        )
                        last_reported_percent = percent
                        last_reported_bytes = downloaded

        LOGGER.info("Downloaded SDE archive to %s.", destination)
        return destination

    def _head_archive(self, build_number: int) -> tuple[str | None, str | None]:
        archive_url = (
            "https://developers.eveonline.com/static-data/tranquility/"
            f"eve-online-static-data-{build_number}-jsonl.zip"
        )
        request = urllib.request.Request(
            archive_url,
            headers=self._headers(),
            method="HEAD",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return response.headers.get("ETag"), response.headers.get("Last-Modified")
        except Exception:  # pragma: no cover - network fallback
            LOGGER.warning("Unable to read ETag/Last-Modified for %s.", archive_url)
            return None, None

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"User-Agent": "Eve-Craft-SDE-Client/1.0"}

    @staticmethod
    def _parse_content_length(value: str | None) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @classmethod
    def _should_report_download_progress(
        cls,
        downloaded: int,
        total_size: int | None,
        percent: int | None,
        last_reported_percent: int | None,
        last_reported_bytes: int,
    ) -> bool:
        if total_size is not None and total_size > 0:
            return percent != last_reported_percent or downloaded >= total_size

        return last_reported_bytes == 0 or downloaded - last_reported_bytes >= cls._UNKNOWN_SIZE_REPORT_STEP


