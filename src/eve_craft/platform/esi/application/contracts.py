from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Protocol

from eve_craft.platform.esi.domain.models import (
    CachedEsiResponse,
    EsiResponseEnvelope,
    EsiSyncCheckpoint,
)


class TokenProvider(Protocol):
    def get_valid_access_token(
        self,
        character_id: int,
        *,
        required_scopes: tuple[str, ...] | list[str] = (),
    ) -> str: ...


class CacheRepository(Protocol):
    def get(self, cache_key: str) -> CachedEsiResponse | None: ...

    def put(
        self,
        cache_key: str,
        *,
        operation_key: str,
        context_key: str,
        payload: object | None,
        status_code: int,
        requested_at: datetime,
        etag: str | None,
        expires_at: datetime | None,
        last_modified: datetime | None,
        pagination,
    ) -> None: ...

    def count(self) -> int: ...

    def latest_requested_at(self) -> datetime | None: ...


class SyncStateRepository(Protocol):
    def get(self, operation_key: str, context_key: str) -> EsiSyncCheckpoint | None: ...

    def save(self, checkpoint: EsiSyncCheckpoint) -> EsiSyncCheckpoint: ...

    def count(self) -> int: ...


PayloadSink = Callable[[EsiResponseEnvelope], None]
