from __future__ import annotations

from sqlalchemy import select

from iph2.platform.db.models import AppBase, AppInstallationInfo
from iph2.platform.db.session import DatabaseManager


class AppDatabaseService:
    def __init__(self, database: DatabaseManager, application_name: str) -> None:
        self._database = database
        self._application_name = application_name

    @property
    def database(self) -> DatabaseManager:
        return self._database

    def ensure_initialized(self) -> None:
        AppBase.metadata.create_all(self._database.engine)

        with self._database.create_session() as session:
            installation_info = session.scalar(select(AppInstallationInfo).limit(1))
            if installation_info is None:
                installation_info = AppInstallationInfo(application_name=self._application_name)
                session.add(installation_info)
                session.commit()
