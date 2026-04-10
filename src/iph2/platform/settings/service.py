from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsService:
    def __init__(self, settings_path: Path) -> None:
        self._settings_path = settings_path
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, Any]:
        if not self._settings_path.exists():
            return {}

        with self._settings_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, payload: dict[str, Any]) -> None:
        with self._settings_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)

    def get(self, key: str, default: Any = None) -> Any:
        return self.load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        payload = self.load()
        payload[key] = value
        self.save(payload)

    def describe_profile(self, profile_name: str) -> str:
        return (
            f"The '{profile_name}' profile belongs to the application settings layer. "
            "The menu action is connected, but the concrete profile editor is not implemented yet."
        )
