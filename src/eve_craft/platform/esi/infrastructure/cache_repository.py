from __future__ import annotations

import json
from datetime import timezone

from sqlalchemy import desc, select

from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.domain.models import CachedEsiResponse, EsiPaginationState
from eve_craft.platform.esi.domain.pagination import EsiPaginationMode
from eve_craft.platform.esi.infrastructure.models import EsiCacheRecord


def _ensure_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


class EsiCacheRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def get(self, cache_key: str) -> CachedEsiResponse | None:
        with self._database.create_session() as session:
            record = session.scalar(select(EsiCacheRecord).where(EsiCacheRecord.cache_key == cache_key).limit(1))

        if record is None:
            return None

        payload = json.loads(record.payload_json) if record.payload_json is not None else None
        return CachedEsiResponse(
            cache_key=record.cache_key,
            operation_key=record.operation_key,
            context_key=record.context_key,
            payload=payload,
            status_code=record.status_code,
            requested_at=_ensure_utc(record.requested_at),
            etag=record.etag,
            expires_at=_ensure_utc(record.expires_at),
            last_modified=_ensure_utc(record.last_modified),
            pagination=EsiPaginationState(
                mode=EsiPaginationMode(record.pagination_mode),
                current_page=record.current_page,
                total_pages=record.total_pages,
                next_page=record.next_page,
                next_before=record.next_before,
                next_after=record.next_after,
                next_from_id=record.next_from_id,
                item_count=record.item_count,
            ),
        )

    def put(
        self,
        cache_key: str,
        *,
        operation_key: str,
        context_key: str,
        payload: object | None,
        status_code: int,
        requested_at,
        etag: str | None,
        expires_at,
        last_modified,
        pagination: EsiPaginationState,
    ) -> None:
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True) if payload is not None else None
        with self._database.create_session() as session:
            record = session.scalar(select(EsiCacheRecord).where(EsiCacheRecord.cache_key == cache_key).limit(1))
            if record is None:
                record = EsiCacheRecord(
                    cache_key=cache_key,
                    operation_key=operation_key,
                    context_key=context_key,
                    payload_json=payload_json,
                    pagination_mode=pagination.mode.value,
                    status_code=status_code,
                    requested_at=requested_at,
                    etag=etag,
                    expires_at=expires_at,
                    last_modified=last_modified,
                    current_page=pagination.current_page,
                    total_pages=pagination.total_pages,
                    next_page=pagination.next_page,
                    next_before=pagination.next_before,
                    next_after=pagination.next_after,
                    next_from_id=pagination.next_from_id,
                    item_count=pagination.item_count,
                )
                session.add(record)
            else:
                record.operation_key = operation_key
                record.context_key = context_key
                record.payload_json = payload_json
                record.pagination_mode = pagination.mode.value
                record.status_code = status_code
                record.requested_at = requested_at
                record.etag = etag
                record.expires_at = expires_at
                record.last_modified = last_modified
                record.current_page = pagination.current_page
                record.total_pages = pagination.total_pages
                record.next_page = pagination.next_page
                record.next_before = pagination.next_before
                record.next_after = pagination.next_after
                record.next_from_id = pagination.next_from_id
                record.item_count = pagination.item_count

            session.commit()

    def count(self) -> int:
        with self._database.create_session() as session:
            records = tuple(session.scalars(select(EsiCacheRecord.cache_key)).all())

        return len(records)

    def latest_requested_at(self):
        with self._database.create_session() as session:
            record = session.scalar(select(EsiCacheRecord).order_by(desc(EsiCacheRecord.requested_at)).limit(1))

        if record is None:
            return None

        return _ensure_utc(record.requested_at)
