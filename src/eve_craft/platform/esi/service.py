from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping

from eve_craft.app.config import AppConfig
from eve_craft.platform.auth.service import AuthService
from eve_craft.platform.characters.settings_keys import DEFAULT_CHARACTER_SETTING_KEY
from eve_craft.platform.db.session import DatabaseManager
from eve_craft.platform.esi.application.request_executor import EsiRequestExecutor
from eve_craft.platform.esi.application.sync_orchestrator import EsiSyncOrchestrator
from eve_craft.platform.esi.domain.models import (
    EsiOperationDescriptor,
    EsiRequestContext,
    EsiResponseEnvelope,
    EsiStatus,
)
from eve_craft.platform.esi.domain.pagination import EsiAuthMode
from eve_craft.platform.esi.domain.scopes import SUPPORTED_ESI_SCOPES
from eve_craft.platform.esi.infrastructure.cache_repository import EsiCacheRepository
from eve_craft.platform.esi.infrastructure.http_client import EsiHttpClient
from eve_craft.platform.esi.infrastructure.route_catalog import EsiRouteCatalog
from eve_craft.platform.esi.infrastructure.sync_state_repository import EsiSyncStateRepository
from eve_craft.platform.esi.infrastructure.throttling import InMemoryEsiThrottler
from eve_craft.platform.settings.service import SettingsService


class EsiService:
    def __init__(self, config: AppConfig, database: DatabaseManager, auth: AuthService, settings: SettingsService) -> None:
        self._config = config
        self._auth = auth
        self._settings = settings
        self._route_catalog = EsiRouteCatalog()
        self._cache_repository = EsiCacheRepository(database)
        self._sync_state_repository = EsiSyncStateRepository(database)
        self._throttler = InMemoryEsiThrottler()
        self._executor = EsiRequestExecutor(
            http_client=EsiHttpClient(
                base_url=config.esi.base_url,
                timeout_seconds=config.esi.request_timeout_seconds,
            ),
            token_provider=auth,
            cache_repository=self._cache_repository,
            throttler=self._throttler,
            compatibility_date=config.esi.compatibility_date,
            user_agent=config.esi.user_agent,
        )
        self._sync_orchestrator = EsiSyncOrchestrator(
            executor=self._executor,
            sync_state_repository=self._sync_state_repository,
            throttler=self._throttler,
        )

    def register_operation(self, operation: EsiOperationDescriptor) -> EsiOperationDescriptor:
        return self._route_catalog.register(operation)

    def get_operation(self, key: str) -> EsiOperationDescriptor:
        return self._route_catalog.get(key)

    def execute(
        self,
        operation: str | EsiOperationDescriptor,
        *,
        route_params: Mapping[str, object] | None = None,
        query_params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        character_id: int | None = None,
        force_refresh: bool = False,
        context_key: str | None = None,
    ) -> EsiResponseEnvelope:
        descriptor = self._resolve_operation(operation)
        return self._executor.execute(
            self._build_request_context(
                descriptor,
                route_params=route_params,
                query_params=query_params,
                json_body=json_body,
                character_id=character_id,
                force_refresh=force_refresh,
                context_key=context_key,
            )
        )

    def iterate_pages(
        self,
        operation: str | EsiOperationDescriptor,
        *,
        route_params: Mapping[str, object] | None = None,
        query_params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        character_id: int | None = None,
        force_refresh: bool = False,
        context_key: str | None = None,
    ) -> Iterator[EsiResponseEnvelope]:
        descriptor = self._resolve_operation(operation)
        context = self._build_request_context(
            descriptor,
            route_params=route_params,
            query_params=query_params,
            json_body=json_body,
            character_id=character_id,
            force_refresh=force_refresh,
            context_key=context_key,
        )
        return self._sync_orchestrator.iterate(context)

    def sync_to_sink(
        self,
        operation: str | EsiOperationDescriptor,
        sink: Callable[[EsiResponseEnvelope], None],
        *,
        route_params: Mapping[str, object] | None = None,
        query_params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        character_id: int | None = None,
        force_refresh: bool = False,
        context_key: str | None = None,
    ) -> int:
        descriptor = self._resolve_operation(operation)
        context = self._build_request_context(
            descriptor,
            route_params=route_params,
            query_params=query_params,
            json_body=json_body,
            character_id=character_id,
            force_refresh=force_refresh,
            context_key=context_key,
        )
        return self._sync_orchestrator.consume(context, sink)

    def supported_scopes(self) -> tuple[str, ...]:
        return SUPPORTED_ESI_SCOPES

    def get_status(self) -> EsiStatus:
        auth_status = self._auth.get_status()
        return EsiStatus(
            compatibility_date=self._config.esi.compatibility_date,
            user_agent=self._config.esi.user_agent,
            configured=auth_status.configured,
            registered_operations=len(self._route_catalog.all()),
            authorized_characters=auth_status.authorized_characters,
            cache_entries=self._cache_repository.count(),
            sync_points=self._sync_state_repository.count(),
            last_request_at=self._cache_repository.latest_requested_at(),
        )

    def describe_status(self) -> str:
        status = self.get_status()
        configuration_text = "configured" if status.configured else "not configured"
        return (
            f"ESI module is {configuration_text}. "
            f"Compatibility date: {status.compatibility_date}. "
            f"Authorized characters: {status.authorized_characters}. "
            f"Registered operations: {status.registered_operations}. "
            f"Cached responses: {status.cache_entries}. "
            f"Sync checkpoints: {status.sync_points}."
        )

    def _resolve_operation(self, operation: str | EsiOperationDescriptor) -> EsiOperationDescriptor:
        if isinstance(operation, EsiOperationDescriptor):
            return operation

        return self._route_catalog.get(operation)

    def _build_request_context(
        self,
        descriptor: EsiOperationDescriptor,
        *,
        route_params: Mapping[str, object] | None = None,
        query_params: Mapping[str, object] | None = None,
        json_body: object | None = None,
        character_id: int | None = None,
        force_refresh: bool = False,
        context_key: str | None = None,
    ) -> EsiRequestContext:
        resolved_character_id = self._resolve_character_id(descriptor, character_id, route_params)
        resolved_route_params = dict(route_params or {})
        if resolved_character_id is not None and "character_id" not in resolved_route_params and "{character_id}" in descriptor.path:
            resolved_route_params["character_id"] = resolved_character_id

        return EsiRequestContext(
            operation=descriptor,
            route_params=resolved_route_params,
            query_params=query_params or {},
            json_body=json_body,
            character_id=resolved_character_id,
            datasource="tranquility",
            force_refresh=force_refresh,
            context_key=context_key,
        )

    def _resolve_character_id(
        self,
        descriptor: EsiOperationDescriptor,
        character_id: int | None,
        route_params: Mapping[str, object] | None,
    ) -> int | None:
        if descriptor.auth_mode != EsiAuthMode.CHARACTER:
            return character_id

        if character_id is not None:
            return character_id

        if route_params is not None and route_params.get("character_id") is not None:
            try:
                return int(route_params["character_id"])
            except (TypeError, ValueError):
                return None

        default_character_id = self._load_default_character_id()
        authorized_characters = self._auth.list_authorized_characters()
        authorized_ids = {character.character_id for character in authorized_characters}
        if default_character_id in authorized_ids:
            return default_character_id

        if not authorized_characters:
            return None

        fallback_character_id = authorized_characters[0].character_id
        self._settings.set(DEFAULT_CHARACTER_SETTING_KEY, fallback_character_id)
        return fallback_character_id

    def _load_default_character_id(self) -> int | None:
        value = self._settings.get(DEFAULT_CHARACTER_SETTING_KEY)
        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None
