from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OperationProgress:
    stage: str
    message: str
    percent: int | None = None
    detail: str | None = None
    indeterminate: bool = False

    def clamp_percent(self) -> int | None:
        if self.percent is None:
            return None

        return max(0, min(100, self.percent))
