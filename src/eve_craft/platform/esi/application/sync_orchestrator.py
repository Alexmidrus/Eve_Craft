from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

from eve_craft.platform.esi.application.contracts import PayloadSink, SyncStateRepository
from eve_craft.platform.esi.application.page_collectors import (
    collect_cursor,
    collect_from_id,
    collect_single,
    collect_x_pages,
)
from eve_craft.platform.esi.application.request_executor import EsiRequestExecutor
from eve_craft.platform.esi.domain.models import EsiRequestContext, EsiResponseEnvelope, EsiSyncCheckpoint
from eve_craft.platform.esi.domain.pagination import EsiPaginationMode
from eve_craft.platform.esi.infrastructure.throttling import InMemoryEsiThrottler


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EsiSyncOrchestrator:
    def __init__(
        self,
        *,
        executor: EsiRequestExecutor,
        sync_state_repository: SyncStateRepository,
        throttler: InMemoryEsiThrottler,
    ) -> None:
        self._executor = executor
        self._sync_state_repository = sync_state_repository
        self._throttler = throttler

    def iterate(self, context: EsiRequestContext) -> Iterator[EsiResponseEnvelope]:
        checkpoint = self._sync_state_repository.get(context.operation.key, context.sync_context_key())

        if context.operation.pagination_mode == EsiPaginationMode.X_PAGES:
            start_page = checkpoint.next_page if checkpoint and not context.force_refresh else None
            iterator = collect_x_pages(
                self._executor,
                context,
                start_page=start_page,
                throttler=self._throttler,
            )
        elif context.operation.pagination_mode == EsiPaginationMode.CURSOR:
            start_before = None
            start_after = None
            if checkpoint and not context.force_refresh:
                if context.operation.cursor_initial_direction.value == "before":
                    start_before = checkpoint.next_before
                else:
                    start_after = checkpoint.next_after
            iterator = collect_cursor(
                self._executor,
                context,
                start_before=start_before,
                start_after=start_after,
            )
        elif context.operation.pagination_mode == EsiPaginationMode.FROM_ID:
            start_from_id = checkpoint.next_from_id if checkpoint and not context.force_refresh else None
            iterator = collect_from_id(
                self._executor,
                context,
                start_from_id=start_from_id,
            )
        else:
            iterator = collect_single(self._executor, context)

        for envelope in iterator:
            self._sync_state_repository.save(
                EsiSyncCheckpoint(
                    operation_key=context.operation.key,
                    context_key=context.sync_context_key(),
                    pagination_mode=context.operation.pagination_mode,
                    next_page=envelope.pagination.next_page,
                    total_pages=envelope.pagination.total_pages,
                    next_before=envelope.pagination.next_before,
                    next_after=envelope.pagination.next_after,
                    next_from_id=envelope.pagination.next_from_id,
                    last_success_at=_utc_now(),
                )
            )
            yield envelope

    def consume(self, context: EsiRequestContext, sink: PayloadSink) -> int:
        count = 0
        for envelope in self.iterate(context):
            sink(envelope)
            count += 1
        return count
