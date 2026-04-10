from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ModuleKind = Literal["feature", "service"]


@dataclass(frozen=True, slots=True)
class ModuleDescriptor:
    key: str
    display_name: str
    kind: ModuleKind
    root_package: str
    tab_object_name: str | None = None
