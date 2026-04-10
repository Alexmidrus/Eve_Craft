from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if any(getattr(handler, "_iph2_handler", False) for handler in root_logger.handlers):
        return root_logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    file_handler = logging.FileHandler(logs_dir / "iph2.log", encoding="utf-8")

    for handler in (console_handler, file_handler):
        handler.setFormatter(formatter)
        handler._iph2_handler = True
        root_logger.addHandler(handler)

    return root_logger
