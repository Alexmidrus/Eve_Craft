from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from eve_craft.platform.db.models import AppBase
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.application.request_executor import EsiRequestExecutor
from eve_craft.platform.esi.domain.models import (
    CachedEsiResponse,
    EsiOperationDescriptor,
    EsiPaginationState,
    EsiRequestContext,
)
from eve_craft.platform.esi.domain.pagination import EsiAuthMode, EsiPaginationMode
from eve_craft.platform.esi.domain.rate_limits import EsiRateLimitSnapshot
from eve_craft.platform.esi.infrastructure.cache_repository import EsiCacheRepository
from eve_craft.platform.esi.infrastructure.http_client import RawEsiResponse
from eve_craft.platform.esi.infrastructure.sync_state_repository import EsiSyncStateRepository
from eve_craft.platform.esi.infrastructure.throttling import InMemoryEsiThrottler


class FakeTokenProvider:
    def __init__(self) -> None:
        self.requests: list[tuple[int, tuple[str, ...]]] = []

    def get_valid_access_token(self, character_id: int, *, required_scopes=()) -> str:
        self.requests.append((character_id, tuple(required_scopes)))
        return "token-123"


class FakeHttpClient:
    def __init__(self, responses: list[RawEsiResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def request(self, *, method: str, path: str, query_params, headers, json_body=None) -> RawEsiResponse:
        self.calls += 1
        return self._responses.pop(0)


class RequestExecutorTests(unittest.TestCase):
    def test_execute_uses_fresh_cache_without_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "app.sqlite3")
            AppBase.metadata.create_all(database.engine)
            cache_repository = EsiCacheRepository(database)
            token_provider = FakeTokenProvider()
            http_client = FakeHttpClient([])
            executor = EsiRequestExecutor(
                http_client=http_client,
                token_provider=token_provider,
                cache_repository=cache_repository,
                throttler=InMemoryEsiThrottler(),
                compatibility_date="2026-04-11",
                user_agent="EveCraft/test",
            )
            operation = EsiOperationDescriptor(
                key="public.status",
                method="GET",
                path="/status/",
                pagination_mode=EsiPaginationMode.SINGLE,
            )
            context = EsiRequestContext(operation=operation)

            cache_repository.put(
                context.cache_key(),
                operation_key=operation.key,
                context_key=context.sync_context_key(),
                payload={"ok": True},
                status_code=200,
                requested_at=datetime.now(timezone.utc),
                etag='"abc"',
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
                last_modified=None,
                pagination=EsiPaginationState(mode=EsiPaginationMode.SINGLE, item_count=1),
            )

            envelope = executor.execute(context)

            self.assertEqual("cache", envelope.source)
            self.assertEqual({"ok": True}, envelope.payload)
            self.assertEqual(0, http_client.calls)
            database.dispose()

    def test_execute_revalidates_cache_on_304(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "app.sqlite3")
            AppBase.metadata.create_all(database.engine)
            cache_repository = EsiCacheRepository(database)
            token_provider = FakeTokenProvider()
            http_client = FakeHttpClient(
                [
                    RawEsiResponse(
                        status_code=304,
                        payload=None,
                        headers={"ETag": '"abc"', "Expires": "Wed, 11 Apr 2026 12:30:00 GMT"},
                        requested_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                        url="https://esi.evetech.net/latest/status/",
                    )
                ]
            )
            executor = EsiRequestExecutor(
                http_client=http_client,
                token_provider=token_provider,
                cache_repository=cache_repository,
                throttler=InMemoryEsiThrottler(),
                compatibility_date="2026-04-11",
                user_agent="EveCraft/test",
            )
            operation = EsiOperationDescriptor(key="public.status", method="GET", path="/status/")
            context = EsiRequestContext(operation=operation)

            cache_repository.put(
                context.cache_key(),
                operation_key=operation.key,
                context_key=context.sync_context_key(),
                payload={"cached": "payload"},
                status_code=200,
                requested_at=datetime(2026, 4, 11, 11, 55, tzinfo=timezone.utc),
                etag='"abc"',
                expires_at=datetime(2026, 4, 11, 12, 5, tzinfo=timezone.utc),
                last_modified=None,
                pagination=EsiPaginationState(mode=EsiPaginationMode.SINGLE),
            )

            envelope = executor.execute(
                EsiRequestContext(operation=operation, force_refresh=True)
            )

            self.assertEqual("cache", envelope.source)
            self.assertEqual({"cached": "payload"}, envelope.payload)
            self.assertEqual(1, http_client.calls)
            database.dispose()

    def test_execute_parses_x_pages_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "app.sqlite3")
            AppBase.metadata.create_all(database.engine)
            executor = EsiRequestExecutor(
                http_client=FakeHttpClient(
                    [
                        RawEsiResponse(
                            status_code=200,
                            payload=[{"id": 1}, {"id": 2}],
                            headers={"X-Pages": "7", "Expires": "Wed, 11 Apr 2026 12:30:00 GMT"},
                            requested_at=datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc),
                            url="https://esi.evetech.net/latest/markets/orders/",
                        )
                    ]
                ),
                token_provider=FakeTokenProvider(),
                cache_repository=EsiCacheRepository(database),
                throttler=InMemoryEsiThrottler(),
                compatibility_date="2026-04-11",
                user_agent="EveCraft/test",
            )
            operation = EsiOperationDescriptor(
                key="market.orders",
                method="GET",
                path="/markets/{region_id}/orders/",
                pagination_mode=EsiPaginationMode.X_PAGES,
            )
            envelope = executor.execute(
                EsiRequestContext(
                    operation=operation,
                    route_params={"region_id": 10000002},
                    query_params={"page": 3},
                )
            )

            self.assertEqual(3, envelope.pagination.current_page)
            self.assertEqual(7, envelope.pagination.total_pages)
            self.assertEqual(4, envelope.pagination.next_page)
            database.dispose()

    def test_execute_adds_bearer_token_for_character_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "app.sqlite3")
            AppBase.metadata.create_all(database.engine)
            token_provider = FakeTokenProvider()
            http_client = FakeHttpClient(
                [
                    RawEsiResponse(
                        status_code=200,
                        payload={"ok": True},
                        headers={},
                        requested_at=datetime.now(timezone.utc),
                        url="https://esi.evetech.net/latest/characters/90000001/assets/",
                    )
                ]
            )
            executor = EsiRequestExecutor(
                http_client=http_client,
                token_provider=token_provider,
                cache_repository=EsiCacheRepository(database),
                throttler=InMemoryEsiThrottler(),
                compatibility_date="2026-04-11",
                user_agent="EveCraft/test",
            )
            operation = EsiOperationDescriptor(
                key="character.assets",
                method="GET",
                path="/characters/{character_id}/assets/",
                auth_mode=EsiAuthMode.CHARACTER,
                required_scopes=("esi-assets.read_assets.v1",),
            )

            envelope = executor.execute(
                EsiRequestContext(
                    operation=operation,
                    route_params={"character_id": 90000001},
                    character_id=90000001,
                )
            )

            self.assertEqual({"ok": True}, envelope.payload)
            self.assertEqual([(90000001, ("esi-assets.read_assets.v1",))], token_provider.requests)
            database.dispose()


class SyncStateRepositoryTests(unittest.TestCase):
    def test_repository_round_trips_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = DatabaseManager(Path(temp_dir) / "app.sqlite3")
            AppBase.metadata.create_all(database.engine)
            repository = EsiSyncStateRepository(database)

            from eve_craft.platform.esi.domain.models import EsiSyncCheckpoint

            checkpoint = EsiSyncCheckpoint(
                operation_key="market.orders",
                context_key="market.orders:test",
                pagination_mode=EsiPaginationMode.X_PAGES,
                next_page=5,
                total_pages=7,
            )
            repository.save(checkpoint)
            restored = repository.get("market.orders", "market.orders:test")

            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(5, restored.next_page)
            self.assertEqual(7, restored.total_pages)
            self.assertEqual(1, repository.count())
            database.dispose()
