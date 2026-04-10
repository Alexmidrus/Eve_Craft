from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from iph2.platform.sde.application.synchronizer import SdeSynchronizer
from iph2.platform.sde.domain.models import InstalledSdeVersion, SdeRemoteVersion


class FakeRepository:
    def __init__(self, installed: InstalledSdeVersion | None, database_path: Path) -> None:
        self._installed = installed
        self.database_path = database_path

    def read_installed_version(self) -> InstalledSdeVersion | None:
        return self._installed

    def activate_database(self, imported_database_path: Path) -> Path:
        self.database_path = imported_database_path
        return imported_database_path


class FakeClient:
    def __init__(self, latest: SdeRemoteVersion | None = None, error: Exception | None = None) -> None:
        self._latest = latest
        self._error = error

    def fetch_latest_version(self) -> SdeRemoteVersion:
        if self._error is not None:
            raise self._error
        assert self._latest is not None
        return self._latest

    def download_archive(self, version: SdeRemoteVersion, destination: Path, report_progress) -> Path:
        destination.write_bytes(b"archive")
        return destination


class FakeImporter:
    def import_archive(self, archive_path: Path, version: SdeRemoteVersion, report_progress) -> Path:
        target_path = archive_path.parent / f"{version.build_number}.sqlite3"
        target_path.write_bytes(b"db")
        return target_path


class SdeSynchronizerTests(unittest.TestCase):
    def test_ensure_ready_uses_local_build_if_remote_check_fails(self) -> None:
        installed = InstalledSdeVersion(
            build_number=111,
            release_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
            imported_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository(installed=installed, database_path=Path(temp_dir) / "sde.sqlite3")
            synchronizer = SdeSynchronizer(
                repository=repository,
                client=FakeClient(error=RuntimeError("network error")),
                importer=FakeImporter(),
                downloads_dir=Path(temp_dir) / "downloads",
            )

            result = synchronizer.ensure_ready(lambda _progress: None)

            self.assertFalse(result.updated)
            self.assertTrue(result.status.available)
            self.assertIn("Continuing", result.status.message)

    def test_ensure_ready_raises_if_no_local_build_and_remote_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository(installed=None, database_path=Path(temp_dir) / "sde.sqlite3")
            synchronizer = SdeSynchronizer(
                repository=repository,
                client=FakeClient(error=RuntimeError("network error")),
                importer=FakeImporter(),
                downloads_dir=Path(temp_dir) / "downloads",
            )

            with self.assertRaises(RuntimeError):
                synchronizer.ensure_ready(lambda _progress: None)
