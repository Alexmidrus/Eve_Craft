from __future__ import annotations

from collections.abc import Iterator

from eve_craft.platform.esi.application.request_executor import EsiRequestExecutor
from eve_craft.platform.esi.domain.models import EsiRequestContext, EsiResponseEnvelope
from eve_craft.platform.esi.domain.pagination import CursorDirection
from eve_craft.platform.esi.infrastructure.throttling import InMemoryEsiThrottler


def collect_single(
    executor: EsiRequestExecutor,
    context: EsiRequestContext,
) -> Iterator[EsiResponseEnvelope]:
    yield executor.execute(context)


def collect_x_pages(
    executor: EsiRequestExecutor,
    context: EsiRequestContext,
    *,
    start_page: int | None,
    throttler: InMemoryEsiThrottler,
) -> Iterator[EsiResponseEnvelope]:
    current_page = start_page or int(context.resolved_query_params().get("page", 1))
    first_page = True
    while True:
        query = dict(context.query_params)
        query["page"] = current_page
        envelope = executor.execute(
            EsiRequestContext(
                operation=context.operation,
                route_params=context.route_params,
                query_params=query,
                json_body=context.json_body,
                character_id=context.character_id,
                datasource=context.datasource,
                force_refresh=context.force_refresh,
                context_key=context.context_key,
            )
        )
        if (
            first_page
            and envelope.expires_at is not None
            and envelope.pagination.total_pages
            and envelope.pagination.total_pages > 1
        ):
            seconds_to_expiry = int((envelope.expires_at - envelope.requested_at).total_seconds())
            if seconds_to_expiry <= context.operation.x_pages_expiry_safety_window_seconds:
                throttler.sleep_seconds(max(seconds_to_expiry + 1, 1))
                envelope = executor.execute(
                    EsiRequestContext(
                        operation=context.operation,
                        route_params=context.route_params,
                        query_params=query,
                        json_body=context.json_body,
                        character_id=context.character_id,
                        datasource=context.datasource,
                        force_refresh=True,
                        context_key=context.context_key,
                    )
                )
        yield envelope
        first_page = False
        if envelope.pagination.next_page is None:
            break
        current_page = envelope.pagination.next_page


def collect_cursor(
    executor: EsiRequestExecutor,
    context: EsiRequestContext,
    *,
    start_before: str | None,
    start_after: str | None,
) -> Iterator[EsiResponseEnvelope]:
    query = dict(context.query_params)
    if start_before is not None and "before" not in query:
        query["before"] = start_before
    if start_after is not None and "after" not in query:
        query["after"] = start_after

    if "before" in query:
        direction = CursorDirection.BEFORE
    elif "after" in query:
        direction = CursorDirection.AFTER
    else:
        direction = context.operation.cursor_initial_direction

    while True:
        envelope = executor.execute(
            EsiRequestContext(
                operation=context.operation,
                route_params=context.route_params,
                query_params=query,
                json_body=context.json_body,
                character_id=context.character_id,
                datasource=context.datasource,
                force_refresh=context.force_refresh,
                context_key=context.context_key,
            )
        )
        yield envelope
        next_token = (
            envelope.pagination.next_before if direction == CursorDirection.BEFORE else envelope.pagination.next_after
        )
        if not next_token or not envelope.pagination.item_count:
            break
        query[direction.value] = next_token


def collect_from_id(
    executor: EsiRequestExecutor,
    context: EsiRequestContext,
    *,
    start_from_id: str | None,
) -> Iterator[EsiResponseEnvelope]:
    current_from_id = start_from_id or (
        str(context.query_params.get("from_id")) if context.query_params.get("from_id") is not None else None
    )

    while True:
        query = dict(context.query_params)
        if current_from_id is not None:
            query["from_id"] = current_from_id
        envelope = executor.execute(
            EsiRequestContext(
                operation=context.operation,
                route_params=context.route_params,
                query_params=query,
                json_body=context.json_body,
                character_id=context.character_id,
                datasource=context.datasource,
                force_refresh=context.force_refresh,
                context_key=context.context_key,
            )
        )
        yield envelope
        if not envelope.pagination.item_count or envelope.pagination.next_from_id is None:
            break
        if envelope.pagination.next_from_id == current_from_id:
            break
        current_from_id = envelope.pagination.next_from_id

