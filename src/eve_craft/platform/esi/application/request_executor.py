from __future__ import annotations

import email.utils
from datetime import datetime, timezone
from typing import Any

from eve_craft.platform.esi.application.contracts import CacheRepository, TokenProvider
from eve_craft.platform.esi.domain.errors import (
    EsiAuthenticationError,
    EsiCacheMissError,
    EsiConfigurationError,
    EsiHttpError,
    EsiRateLimitedError,
)
from eve_craft.platform.esi.domain.models import (
    CachedEsiResponse,
    EsiPaginationState,
    EsiRequestContext,
    EsiResponseEnvelope,
)
from eve_craft.platform.esi.domain.pagination import EsiAuthMode, EsiPaginationMode
from eve_craft.platform.esi.domain.rate_limits import EsiRateLimitSnapshot, parse_rate_limit_snapshot
from eve_craft.platform.esi.infrastructure.http_client import EsiHttpClient, RawEsiResponse
from eve_craft.platform.esi.infrastructure.throttling import InMemoryEsiThrottler


def _parse_http_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    parsed = email.utils.parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


class EsiRequestExecutor:
    def __init__(
        self,
        *,
        http_client: EsiHttpClient,
        token_provider: TokenProvider,
        cache_repository: CacheRepository,
        throttler: InMemoryEsiThrottler,
        compatibility_date: str,
        user_agent: str,
    ) -> None:
        self._http_client = http_client
        self._token_provider = token_provider
        self._cache_repository = cache_repository
        self._throttler = throttler
        self._compatibility_date = compatibility_date
        self._user_agent = user_agent

    def execute(self, context: EsiRequestContext) -> EsiResponseEnvelope:
        cache_key = context.cache_key()
        cached = self._cache_repository.get(cache_key) if context.operation.cache_enabled else None
        if cached is not None and cached.is_fresh() and not context.force_refresh:
            return cached.to_envelope(source="cache")

        headers = self._build_headers(context, cached)
        last_error: Exception | None = None

        for attempt in range(context.operation.retry_count + 1):
            try:
                self._throttler.before_request()
                response = self._http_client.request(
                    method=context.operation.method,
                    path=context.resolved_path(),
                    query_params=context.resolved_query_params(),
                    headers=headers,
                    json_body=context.json_body,
                )
            except Exception as error:
                last_error = error
                if attempt >= context.operation.retry_count:
                    raise

                self._throttler.backoff(attempt)
                continue

            snapshot = parse_rate_limit_snapshot(response.headers)
            self._throttler.after_response(snapshot, response.status_code)

            if response.status_code == 304:
                if cached is None or cached.payload is None:
                    raise EsiCacheMissError(
                        "ESI returned 304 Not Modified, but there is no cached payload to reuse locally."
                    )

                envelope = cached.to_envelope(source="cache", rate_limits=snapshot)
                self._cache_repository.put(
                    cache_key,
                    operation_key=context.operation.key,
                    context_key=context.sync_context_key(),
                    payload=cached.payload,
                    status_code=200,
                    requested_at=response.requested_at,
                    etag=response.headers.get("ETag") or cached.etag,
                    expires_at=_parse_http_datetime(response.headers.get("Expires")) or cached.expires_at,
                    last_modified=_parse_http_datetime(response.headers.get("Last-Modified")) or cached.last_modified,
                    pagination=envelope.pagination,
                )
                return envelope

            if 200 <= response.status_code < 300:
                envelope = self._build_envelope(context, response, snapshot)
                if context.operation.cache_enabled:
                    payload = envelope.payload if context.operation.include_payload_in_cache else None
                    self._cache_repository.put(
                        cache_key,
                        operation_key=context.operation.key,
                        context_key=context.sync_context_key(),
                        payload=payload,
                        status_code=envelope.status_code,
                        requested_at=envelope.requested_at,
                        etag=envelope.etag,
                        expires_at=envelope.expires_at,
                        last_modified=envelope.last_modified,
                        pagination=envelope.pagination,
                    )
                return envelope

            if response.status_code in {401, 403}:
                raise EsiAuthenticationError(
                    f"ESI request '{context.operation.key}' was rejected with status {response.status_code}."
                )

            if response.status_code in {420, 429}:
                retry_after_seconds = snapshot.retry_after_seconds or snapshot.error_limit_reset
                if attempt < context.operation.retry_count:
                    self._throttler.backoff(attempt)
                    continue

                raise EsiRateLimitedError(
                    f"ESI request '{context.operation.key}' is rate limited.",
                    status_code=response.status_code,
                    retry_after_seconds=retry_after_seconds,
                    payload=response.payload,
                )

            if response.status_code >= 500 and attempt < context.operation.retry_count:
                self._throttler.backoff(attempt)
                continue

            raise EsiHttpError(
                f"ESI request '{context.operation.key}' failed with status {response.status_code}.",
                status_code=response.status_code,
                payload=response.payload,
            )

        if last_error is not None:
            raise last_error

        raise RuntimeError("Unexpected ESI execution flow reached an impossible state.")

    def _build_headers(self, context: EsiRequestContext, cached: CachedEsiResponse | None) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
            "X-Compatibility-Date": self._compatibility_date,
        }
        if context.operation.auth_mode == EsiAuthMode.CHARACTER:
            if context.character_id is None:
                raise EsiConfigurationError(
                    f"ESI operation '{context.operation.key}' requires a character id for token lookup."
                )
            access_token = self._token_provider.get_valid_access_token(
                context.character_id,
                required_scopes=context.operation.required_scopes,
            )
            headers["Authorization"] = f"Bearer {access_token}"

        if cached is not None:
            if cached.etag:
                headers["If-None-Match"] = cached.etag
            elif cached.last_modified:
                headers["If-Modified-Since"] = email.utils.format_datetime(cached.last_modified, usegmt=True)

        return headers

    def _build_envelope(
        self,
        context: EsiRequestContext,
        response: RawEsiResponse,
        snapshot: EsiRateLimitSnapshot,
    ) -> EsiResponseEnvelope:
        return EsiResponseEnvelope(
            payload=response.payload,
            requested_at=response.requested_at,
            status_code=response.status_code,
            etag=response.headers.get("ETag"),
            expires_at=_parse_http_datetime(response.headers.get("Expires")),
            last_modified=_parse_http_datetime(response.headers.get("Last-Modified")),
            rate_limits=snapshot,
            pagination=self._build_pagination_state(context, response),
            source="network",
        )

    def _build_pagination_state(self, context: EsiRequestContext, response: RawEsiResponse) -> EsiPaginationState:
        mode = context.operation.pagination_mode
        if mode == EsiPaginationMode.X_PAGES:
            current_page = int(context.resolved_query_params().get("page", 1))
            total_pages = self._parse_int(response.headers.get("X-Pages"))
            next_page = current_page + 1 if total_pages is not None and current_page < total_pages else None
            return EsiPaginationState(
                mode=mode,
                current_page=current_page,
                total_pages=total_pages,
                next_page=next_page,
                item_count=self._payload_item_count(response.payload),
            )

        if mode == EsiPaginationMode.CURSOR:
            cursor = {}
            payload = response.payload
            if isinstance(payload, dict):
                cursor = payload.get(context.operation.cursor_object_key, {}) or {}
                items = payload.get(context.operation.cursor_payload_key)
                item_count = self._payload_item_count(items)
            else:
                item_count = self._payload_item_count(payload)

            return EsiPaginationState(
                mode=mode,
                next_before=str(cursor.get("before")) if cursor.get("before") is not None else None,
                next_after=str(cursor.get("after")) if cursor.get("after") is not None else None,
                item_count=item_count,
            )

        if mode == EsiPaginationMode.FROM_ID:
            next_from_id = self._extract_from_id(response.payload, context.operation.from_id_field)
            return EsiPaginationState(
                mode=mode,
                next_from_id=next_from_id,
                item_count=self._payload_item_count(response.payload),
            )

        return EsiPaginationState(
            mode=mode,
            item_count=self._payload_item_count(response.payload),
        )

    @staticmethod
    def _payload_item_count(payload: Any) -> int | None:
        if isinstance(payload, list):
            return len(payload)
        if isinstance(payload, dict):
            return len(payload)
        return None

    @staticmethod
    def _extract_from_id(payload: Any, field_name: str) -> str | None:
        if not isinstance(payload, list) or not payload:
            return None
        last_item = payload[-1]
        if not isinstance(last_item, dict):
            return None
        value = last_item.get(field_name)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

