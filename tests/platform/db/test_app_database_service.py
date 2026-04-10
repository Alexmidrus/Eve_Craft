from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import select

from eve_craft.platform.db.models import AppInstallationInfo
from eve_craft.platform.db.service import AppDatabaseService
from eve_craft.platform.db.session import DatabaseManager


class AppDatabaseServiceTests(unittest.TestCase):
    def test_ensure_initialized_creates_installation_row(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "app.sqlite3"
            database = DatabaseManager(database_path)
            service = AppDatabaseService(database, application_name="Eve Craft")

            service.ensure_initialized()
            service.ensure_initialized()

            with database.create_session() as session:
                installation_info = session.scalar(select(AppInstallationInfo).limit(1))

            self.assertIsNotNone(installation_info)
            self.assertEqual("Eve Craft", installation_info.application_name)

            database.dispose()


