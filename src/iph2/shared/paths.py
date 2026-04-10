from __future__ import annotations

import os
import sys
from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def src_root() -> Path:
    return package_root().parent


def project_root() -> Path:
    return src_root().parent


def default_user_data_dir(app_name: str) -> Path:
    if sys.platform.startswith("win"):
        base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    return base_dir / app_name
