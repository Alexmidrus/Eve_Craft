from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, select

from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.sde.domain.models import InstalledSdeVersion
from eve_craft.platform.sde.infrastructure.models import SdeCatalogInfo

LOGGER = logging.getLogger(__name__)


class SdeMetadataRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @property
    def database_path(self) -> Path:
        return self._database_path

    def read_installed_version(self) -> InstalledSdeVersion | None:
        if not self._database_path.exists():
            return None

        database = DatabaseManager(self._database_path)
        try:
            inspector = inspect(database.engine)
            if not inspector.has_table("sde_catalog_info"):
                return None

            with database.create_session() as session:
                row = session.scalar(select(SdeCatalogInfo).limit(1))
                if row is None:
                    return None

                return InstalledSdeVersion(
                    build_number=row.build_number,
                    release_date=row.release_date,
                    imported_at=row.imported_at,
                    archive_url=row.archive_url,
                    archive_etag=row.archive_etag,
                    archive_last_modified=row.archive_last_modified,
                )
        except Exception:
            LOGGER.exception("Unable to read installed SDE metadata from %s.", self._database_path)
            return None
        finally:
            database.dispose()

    def activate_database(self, imported_database_path: Path) -> Path:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(imported_database_path, self._database_path)
        LOGGER.info("Activated SDE database %s.", self._database_path)
        return self._database_path

    def imported_at(self) -> datetime | None:
        installed = self.read_installed_version()
        if installed is None:
            return None

        return installed.imported_at

