from __future__ import annotations

import os
from pathlib import Path

from eve_craft.shared.paths import project_root


def load_dotenv_file(dotenv_path: Path, *, override: bool = False) -> dict[str, str]:
    loaded: dict[str, str] = {}
    if not dotenv_path.exists():
        return loaded

    for raw_line in dotenv_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.removeprefix("export ").strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = _normalize_env_value(value.strip())
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value

    return loaded


def load_project_dotenv(*, override: bool = False) -> dict[str, str]:
    return load_dotenv_file(project_root() / ".env", override=override)


def _normalize_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]

    return value

