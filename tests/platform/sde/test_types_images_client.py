from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from eve_craft.platform.sde.infrastructure.types_images_client import TypeImageCollectionClient


class _FakeResponse:
    def __init__(self, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        self._buffer = io.BytesIO(body)
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class TypeImageCollectionClientTests(unittest.TestCase):
    def test_fetch_latest_version_reads_types_archive_from_iec_index(self) -> None:
        page = """
        ---
        title: Image Export Collection
        ---
        # (Deprecated) Image Export Collection (IEC)

        Export for `Uprising (V21.03 - March 14th 2023)`
        - [Icons](https://web.ccpgamescdn.com/aws/developers/Uprising_V21.03_Icons.zip)
        - [Renders](https://web.ccpgamescdn.com/aws/developers/Uprising_V21.03_Renders.zip)
        - [Types](https://web.ccpgamescdn.com/aws/developers/Uprising_V21.03_Types.zip)
        """

        def fake_urlopen(request, timeout=30):  # type: ignore[no-untyped-def]
            url = request.full_url
            method = request.get_method()
            if url == TypeImageCollectionClient.SOURCE_URL:
                return _FakeResponse(body=page.encode("utf-8"))
            if url.endswith("_Types.zip") and method == "HEAD":
                return _FakeResponse(
                    headers={
                        "ETag": "etag-123",
                        "Last-Modified": "Wed, 15 Mar 2023 13:08:29 GMT",
                        "Content-Length": "231751250",
                    }
                )
            raise AssertionError(f"Unexpected request: {method} {url}")

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            version = TypeImageCollectionClient().fetch_latest_version()

        self.assertEqual("Uprising (V21.03 - March 14th 2023)", version.release_name)
        self.assertEqual(
            "https://web.ccpgamescdn.com/aws/developers/Uprising_V21.03_Types.zip",
            version.archive_url,
        )
        self.assertEqual(TypeImageCollectionClient.SOURCE_URL, version.source_url)
        self.assertEqual("etag-123", version.etag)
        self.assertEqual("Wed, 15 Mar 2023 13:08:29 GMT", version.last_modified)
        self.assertEqual(231751250, version.content_length)

    def test_should_report_download_progress_when_percent_changes(self) -> None:
        self.assertTrue(
            TypeImageCollectionClient._should_report_download_progress(
                downloaded=1024,
                total_size=10_240,
                percent=10,
                last_reported_percent=None,
                last_reported_bytes=0,
            )
        )
        self.assertFalse(
            TypeImageCollectionClient._should_report_download_progress(
                downloaded=1536,
                total_size=10_240,
                percent=10,
                last_reported_percent=10,
                last_reported_bytes=1024,
            )
        )
        self.assertTrue(
            TypeImageCollectionClient._should_report_download_progress(
                downloaded=2048,
                total_size=10_240,
                percent=20,
                last_reported_percent=10,
                last_reported_bytes=1024,
            )
        )
