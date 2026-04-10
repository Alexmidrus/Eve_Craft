from __future__ import annotations

from pathlib import Path


class SdeService:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def describe_status(self) -> str:
        return (
            "The SDE service is registered in the service layer. "
            f"Default local storage: {self._storage_dir}"
        )
