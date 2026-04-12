from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from eve_craft.platform.esi.domain.rate_limits import EsiRateLimitSnapshot


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryEsiThrottler:
    def __init__(self) -> None:
        self._blocked_until: datetime | None = None
        self._latest_snapshot: EsiRateLimitSnapshot | None = None

    def before_request(self) -> None:
        if self._blocked_until is None:
            return

        now = _utc_now()
        if self._blocked_until <= now:
            self._blocked_until = None
            return

        time.sleep((self._blocked_until - now).total_seconds())
        self._blocked_until = None

    def after_response(self, snapshot: EsiRateLimitSnapshot, status_code: int) -> None:
        self._latest_snapshot = snapshot
        if status_code not in {420, 429}:
            return

        delay = snapshot.retry_after_seconds or snapshot.error_limit_reset or 1
        self._blocked_until = _utc_now() + timedelta(seconds=delay)

    def backoff(self, attempt: int) -> None:
        time.sleep(min(2**attempt, 10))

    def latest_snapshot(self) -> EsiRateLimitSnapshot | None:
        return self._latest_snapshot

    def sleep_seconds(self, seconds: int | float) -> None:
        if seconds > 0:
            time.sleep(seconds)

