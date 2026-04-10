from __future__ import annotations

from sqlalchemy.orm import Session

from iph2.platform.db.session import DatabaseManager


class SqlAlchemyUnitOfWork:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._database.create_session()
        return self

    def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered.")

        self.session.commit()

    def rollback(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of work has not been entered.")

        self.session.rollback()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.session is None:
            return

        if exc_type is not None:
            self.session.rollback()

        self.session.close()
        self.session = None
