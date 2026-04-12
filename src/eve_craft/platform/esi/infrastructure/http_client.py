from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class RawEsiResponse:
    status_code: int
    payload: Any
    headers: dict[str, str]
    requested_at: datetime
    url: str


class EsiHttpClient:
    def __init__(self, base_url: str, timeout_seconds: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def request(
        self,
        *,
        method: str,
        path: str,
        query_params: Mapping[str, object] | None,
        headers: Mapping[str, str],
        json_body: object | None = None,
    ) -> RawEsiResponse:
        query_string = urllib.parse.urlencode(query_params or {}, doseq=True)
        url = f"{self._base_url}/{path.lstrip('/')}"
        if query_string:
            url = f"{url}?{query_string}"

        body = None
        request_headers = dict(headers)
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        request = urllib.request.Request(
            url,
            method=method.upper(),
            data=body,
            headers=request_headers,
        )
        requested_at = _utc_now()

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                return RawEsiResponse(
                    status_code=response.status,
                    payload=self._parse_payload(response.read(), response.headers.get("Content-Type")),
                    headers={key: value for key, value in response.headers.items()},
                    requested_at=requested_at,
                    url=url,
                )
        except urllib.error.HTTPError as error:
            return RawEsiResponse(
                status_code=error.code,
                payload=self._parse_payload(error.read(), error.headers.get("Content-Type")),
                headers={key: value for key, value in error.headers.items()},
                requested_at=requested_at,
                url=url,
            )

    @staticmethod
    def _parse_payload(body: bytes, content_type: str | None) -> Any:
        if not body:
            return None

        lowered_content_type = (content_type or "").lower()
        if "application/json" in lowered_content_type or body[:1] in {b"{", b"["}:
            try:
                return json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                return body.decode("utf-8", errors="replace")

        return body.decode("utf-8", errors="replace")
