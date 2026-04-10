from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool


class DatabaseManager:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(
            f"sqlite:///{self._database_path.resolve().as_posix()}",
            future=True,
            poolclass=NullPool,
            connect_args={
                "timeout": 30,
            },
        )
        self._session_factory = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
            future=True,
        )
        event.listen(self._engine, "connect", self._apply_sqlite_pragmas)

    @property
    def database_path(self) -> Path:
        return self._database_path

    @property
    def engine(self):
        return self._engine

    def create_session(self) -> Session:
        return self._session_factory()

    def dispose(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _apply_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute("PRAGMA busy_timeout = 30000")
            cursor.execute("PRAGMA synchronous = NORMAL")
        finally:
            cursor.close()
