from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


def _read_header(headers: Mapping[str, str], name: str) -> str | None:
    for header_name, header_value in headers.items():
        if header_name.lower() == name.lower():
            return header_value

    return None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class EsiRateLimitSnapshot:
    group: str | None = None
    limit: int | None = None
    remain: int | None = None
    used: int | None = None
    error_limit_remain: int | None = None
    error_limit_reset: int | None = None
    retry_after_seconds: int | None = None


def parse_rate_limit_snapshot(headers: Mapping[str, str]) -> EsiRateLimitSnapshot:
    return EsiRateLimitSnapshot(
        group=_read_header(headers, "X-Ratelimit-Group"),
        limit=_parse_int(_read_header(headers, "X-Ratelimit-Limit")),
        remain=_parse_int(_read_header(headers, "X-Ratelimit-Remain")),
        used=_parse_int(_read_header(headers, "X-Ratelimit-Used")),
        error_limit_remain=_parse_int(_read_header(headers, "X-Esi-Error-Limit-Remain")),
        error_limit_reset=_parse_int(_read_header(headers, "X-Esi-Error-Limit-Reset")),
        retry_after_seconds=_parse_int(_read_header(headers, "Retry-After")),
    )

