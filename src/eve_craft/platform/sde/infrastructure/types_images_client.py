"""Resolve and download the IEC Types image archive published by CCP."""

from __future__ import annotations

import html
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

from eve_craft.platform.sde.domain.models import TypeImageRemoteVersion
from eve_craft.shared.progress import OperationProgress

LOGGER = logging.getLogger(__name__)


class TypeImageCollectionClient:
    """Read IEC Types archive metadata from the published IEC index and download it."""

    SOURCE_URL = "https://raw.githubusercontent.com/esi/esi-docs/main/docs/services/iec/index.md"
    _ARCHIVE_LINK_PATTERN = re.compile(
        r"(?:\[(?P<markdown_label>Types)\]\((?P<markdown_url>https://[^)\s]+_Types\.zip)\)|"
        r'<a href="(?P<html_url>https://[^"]+_Types\.zip)">Types</a>)',
        re.IGNORECASE,
    )
    _QUOTED_RELEASE_PATTERN = re.compile(r"Export for\s*`(?P<release>[^`]+)`")
    _PLAIN_RELEASE_PATTERN = re.compile(r"Export for\s*(?P<release>[^\r\n]+?)(?:\s+-|\s*$)")
    _UNKNOWN_SIZE_REPORT_STEP = 1024 * 1024 * 5

    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout_seconds = timeout_seconds

    def fetch_latest_version(self) -> TypeImageRemoteVersion:
        """Resolve the currently published IEC Types archive from the IEC index."""

        request = urllib.request.Request(self.SOURCE_URL, headers=self._headers())
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            page_content = response.read().decode("utf-8", "replace")

        archive_url = self._extract_archive_url(page_content)
        release_name = self._extract_release_name(page_content, archive_url)
        etag, last_modified, content_length = self._head_archive(archive_url)

        version = TypeImageRemoteVersion(
            release_name=release_name,
            archive_url=archive_url,
            source_url=self.SOURCE_URL,
            etag=etag,
            last_modified=last_modified,
            content_length=content_length,
        )
        LOGGER.info("Resolved IEC Types archive %s.", archive_url)
        return version

    def download_archive(
        self,
        version: TypeImageRemoteVersion,
        destination: Path,
        report_progress,
    ) -> Path:
        """Download the Types archive and emit rate-limited progress updates."""

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
                                stage="types_images_download",
                                message="Downloading IEC Types image archive",
                                percent=percent,
                                detail=f"{downloaded} bytes downloaded",
                                indeterminate=percent is None,
                            )
                        )
                        last_reported_percent = percent
                        last_reported_bytes = downloaded

        LOGGER.info("Downloaded IEC Types archive to %s.", destination)
        return destination

    def _head_archive(self, archive_url: str) -> tuple[str | None, str | None, int | None]:
        """Read optional caching metadata for the archive without downloading it."""

        request = urllib.request.Request(
            archive_url,
            headers=self._headers(),
            method="HEAD",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return (
                    response.headers.get("ETag"),
                    response.headers.get("Last-Modified"),
                    self._parse_content_length(response.headers.get("Content-Length")),
                )
        except Exception:  # pragma: no cover - network fallback
            LOGGER.warning("Unable to read archive headers for %s.", archive_url)
            return None, None, None

    @staticmethod
    def _headers() -> dict[str, str]:
        """Return the request headers shared across IEC requests."""

        return {"User-Agent": "Eve-Craft-IEC-Client/1.0"}

    @staticmethod
    def _parse_content_length(value: str | None) -> int | None:
        """Safely parse an optional content-length header."""

        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    @classmethod
    def _extract_archive_url(cls, page_content: str) -> str:
        """Extract the `Types.zip` link from the published IEC index."""

        match = cls._ARCHIVE_LINK_PATTERN.search(page_content)
        if match is None:
            raise RuntimeError("Unable to resolve the IEC Types archive URL from the CCP documentation page.")

        archive_url = match.group("markdown_url") or match.group("html_url")
        return html.unescape(archive_url)

    @classmethod
    def _extract_release_name(cls, page_content: str, archive_url: str) -> str:
        """Extract a human-readable release name for the current image collection."""

        match = cls._QUOTED_RELEASE_PATTERN.search(page_content)
        if match is None:
            match = cls._PLAIN_RELEASE_PATTERN.search(page_content)
        if match is not None:
            return html.unescape(match.group("release")).strip()

        archive_name = Path(urllib.parse.urlparse(archive_url).path).name
        return archive_name.removesuffix("_Types.zip")

    @classmethod
    def _should_report_download_progress(
        cls,
        downloaded: int,
        total_size: int | None,
        percent: int | None,
        last_reported_percent: int | None,
        last_reported_bytes: int,
    ) -> bool:
        """Decide when the next progress event is useful enough to emit."""

        if total_size is not None and total_size > 0:
            return percent != last_reported_percent or downloaded >= total_size

        return last_reported_bytes == 0 or downloaded - last_reported_bytes >= cls._UNKNOWN_SIZE_REPORT_STEP
