from __future__ import annotations

from sqlalchemy import select

from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.domain.models import EsiSyncCheckpoint
from eve_craft.platform.esi.domain.pagination import EsiPaginationMode
from eve_craft.platform.esi.infrastructure.models import EsiSyncStateRecord


class EsiSyncStateRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def get(self, operation_key: str, context_key: str) -> EsiSyncCheckpoint | None:
        with self._database.create_session() as session:
            record = session.scalar(
                select(EsiSyncStateRecord)
                .where(EsiSyncStateRecord.operation_key == operation_key)
                .where(EsiSyncStateRecord.context_key == context_key)
                .limit(1)
            )

        if record is None:
            return None

        return EsiSyncCheckpoint(
            operation_key=record.operation_key,
            context_key=record.context_key,
            pagination_mode=EsiPaginationMode(record.pagination_mode),
            next_page=record.next_page,
            total_pages=record.total_pages,
            next_before=record.next_before,
            next_after=record.next_after,
            next_from_id=record.next_from_id,
            last_success_at=record.last_success_at,
            last_error_message=record.last_error_message,
        )

    def save(self, checkpoint: EsiSyncCheckpoint) -> EsiSyncCheckpoint:
        with self._database.create_session() as session:
            record = session.scalar(
                select(EsiSyncStateRecord)
                .where(EsiSyncStateRecord.operation_key == checkpoint.operation_key)
                .where(EsiSyncStateRecord.context_key == checkpoint.context_key)
                .limit(1)
            )
            if record is None:
                record = EsiSyncStateRecord(
                    operation_key=checkpoint.operation_key,
                    context_key=checkpoint.context_key,
                    pagination_mode=checkpoint.pagination_mode.value,
                    next_page=checkpoint.next_page,
                    total_pages=checkpoint.total_pages,
                    next_before=checkpoint.next_before,
                    next_after=checkpoint.next_after,
                    next_from_id=checkpoint.next_from_id,
                    last_success_at=checkpoint.last_success_at,
                    last_error_message=checkpoint.last_error_message,
                )
                session.add(record)
            else:
                record.pagination_mode = checkpoint.pagination_mode.value
                record.next_page = checkpoint.next_page
                record.total_pages = checkpoint.total_pages
                record.next_before = checkpoint.next_before
                record.next_after = checkpoint.next_after
                record.next_from_id = checkpoint.next_from_id
                record.last_success_at = checkpoint.last_success_at
                record.last_error_message = checkpoint.last_error_message

            session.commit()

        return checkpoint

    def count(self) -> int:
        with self._database.create_session() as session:
            records = tuple(session.scalars(select(EsiSyncStateRecord.context_key)).all())

        return len(records)

