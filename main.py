from __future__ import annotations

import sys
from pathlib import Path


def _add_src_to_path() -> None:
    project_root = Path(__file__).resolve().parent
    src_root = project_root / "src"

    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def main() -> int:
    _add_src_to_path()

    from eve_craft.main import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())

