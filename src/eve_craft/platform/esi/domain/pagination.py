from __future__ import annotations

from enum import Enum


class EsiPaginationMode(str, Enum):
    SINGLE = "single"
    X_PAGES = "x_pages"
    CURSOR = "cursor"
    FROM_ID = "from_id"


class EsiAuthMode(str, Enum):
    PUBLIC = "public"
    CHARACTER = "character"


class CursorDirection(str, Enum):
    BEFORE = "before"
    AFTER = "after"

