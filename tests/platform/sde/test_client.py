from __future__ import annotations

import unittest

from eve_craft.platform.sde.infrastructure.client import EveStaticDataClient


class EveStaticDataClientTests(unittest.TestCase):
    def test_should_report_download_progress_when_percent_changes(self) -> None:
        self.assertTrue(
            EveStaticDataClient._should_report_download_progress(
                downloaded=1024,
                total_size=10_240,
                percent=10,
                last_reported_percent=None,
                last_reported_bytes=0,
            )
        )
        self.assertFalse(
            EveStaticDataClient._should_report_download_progress(
                downloaded=1536,
                total_size=10_240,
                percent=10,
                last_reported_percent=10,
                last_reported_bytes=1024,
            )
        )
        self.assertTrue(
            EveStaticDataClient._should_report_download_progress(
                downloaded=2048,
                total_size=10_240,
                percent=20,
                last_reported_percent=10,
                last_reported_bytes=1024,
            )
        )

    def test_should_report_unknown_size_downloads_in_large_steps(self) -> None:
        self.assertTrue(
            EveStaticDataClient._should_report_download_progress(
                downloaded=1024,
                total_size=None,
                percent=None,
                last_reported_percent=None,
                last_reported_bytes=0,
            )
        )
        self.assertFalse(
            EveStaticDataClient._should_report_download_progress(
                downloaded=1024 * 1024,
                total_size=None,
                percent=None,
                last_reported_percent=None,
                last_reported_bytes=1024,
            )
        )
        self.assertTrue(
            EveStaticDataClient._should_report_download_progress(
                downloaded=(1024 * 1024 * 5) + 1024,
                total_size=None,
                percent=None,
                last_reported_percent=None,
                last_reported_bytes=1024,
            )
        )

