from __future__ import annotations

import hashlib
import json
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from eve_craft.platform.esi.domain.pagination import CursorDirection, EsiAuthMode, EsiPaginationMode
from eve_craft.platform.esi.domain.rate_limits import EsiRateLimitSnapshot

_PAGINATION_QUERY_KEYS = frozenset({"page", "before", "after", "from_id"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalize_value(inner_value) for key, inner_value in sorted(value.items())}
    if isinstance(value, (tuple, list, set)):
        return [_normalize_value(item) for item in value]
    return value


def _identity_digest(payload: Mapping[str, Any]) -> str:
    normalized = _normalize_value(payload)
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EsiOperationDescriptor:
    key: str
    method: str
    path: str
    auth_mode: EsiAuthMode = EsiAuthMode.PUBLIC
    required_scopes: tuple[str, ...] = ()
    pagination_mode: EsiPaginationMode = EsiPaginationMode.SINGLE
    cache_enabled: bool = True
    include_payload_in_cache: bool = True
    retry_count: int = 2
    cursor_initial_direction: CursorDirection = CursorDirection.BEFORE
    cursor_payload_key: str = "items"
    cursor_object_key: str = "cursor"
    from_id_field: str = "id"
    x_pages_expiry_safety_window_seconds: int = 5


@dataclass(frozen=True, slots=True)
class EsiRequestContext:
    operation: EsiOperationDescriptor
    route_params: Mapping[str, object] = field(default_factory=dict)
    query_params: Mapping[str, object] = field(default_factory=dict)
    json_body: object | None = None
    character_id: int | None = None
    datasource: str = "tranquility"
    force_refresh: bool = False
    context_key: str | None = None

    def resolved_path(self) -> str:
        route_params = {
            str(key): urllib.parse.quote(str(value), safe="")
            for key, value in self.route_params.items()
        }
        return self.operation.path.format(**route_params)

    def resolved_query_params(self) -> dict[str, object]:
        query = {str(key): value for key, value in self.query_params.items() if value is not None}
        if self.datasource and "datasource" not in query:
            query["datasource"] = self.datasource
        return query

    def cache_key(self) -> str:
        return f"{self.operation.key}:{_identity_digest(self._identity_payload(include_pagination=True))}"

    def sync_context_key(self) -> str:
        if self.context_key:
            return self.context_key

        return f"{self.operation.key}:{_identity_digest(self._identity_payload(include_pagination=False))}"

    def _identity_payload(self, *, include_pagination: bool) -> dict[str, Any]:
        if include_pagination:
            query = self.resolved_query_params()
        else:
            query = {
                key: value
                for key, value in self.resolved_query_params().items()
                if key not in _PAGINATION_QUERY_KEYS
            }

        return {
            "character_id": self.character_id,
            "route_params": dict(self.route_params),
            "query_params": query,
            "json_body": self.json_body,
        }


@dataclass(frozen=True, slots=True)
class EsiPaginationState:
    mode: EsiPaginationMode
    current_page: int | None = None
    total_pages: int | None = None
    next_page: int | None = None
    next_before: str | None = None
    next_after: str | None = None
    next_from_id: str | None = None
    item_count: int | None = None


@dataclass(frozen=True, slots=True)
class EsiResponseEnvelope:
    payload: object
    requested_at: datetime
    status_code: int
    etag: str | None
    expires_at: datetime | None
    last_modified: datetime | None
    rate_limits: EsiRateLimitSnapshot
    pagination: EsiPaginationState
    source: str


@dataclass(frozen=True, slots=True)
class CachedEsiResponse:
    cache_key: str
    operation_key: str
    context_key: str
    payload: object | None
    status_code: int
    requested_at: datetime
    etag: str | None
    expires_at: datetime | None
    last_modified: datetime | None
    pagination: EsiPaginationState

    def is_fresh(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False

        now = now or _utc_now()
        return self.expires_at > now

    def to_envelope(
        self,
        *,
        source: str = "cache",
        rate_limits: EsiRateLimitSnapshot | None = None,
    ) -> EsiResponseEnvelope:
        return EsiResponseEnvelope(
            payload=self.payload,
            requested_at=self.requested_at,
            status_code=200,
            etag=self.etag,
            expires_at=self.expires_at,
            last_modified=self.last_modified,
            rate_limits=rate_limits or EsiRateLimitSnapshot(),
            pagination=self.pagination,
            source=source,
        )


@dataclass(frozen=True, slots=True)
class EsiSyncCheckpoint:
    operation_key: str
    context_key: str
    pagination_mode: EsiPaginationMode
    next_page: int | None = None
    total_pages: int | None = None
    next_before: str | None = None
    next_after: str | None = None
    next_from_id: str | None = None
    last_success_at: datetime = field(default_factory=_utc_now)
    last_error_message: str | None = None


@dataclass(frozen=True, slots=True)
class EsiStatus:
    compatibility_date: str
    user_agent: str
    configured: bool
    registered_operations: int
    authorized_characters: int
    cache_entries: int
    sync_points: int
    last_request_at: datetime | None = None
