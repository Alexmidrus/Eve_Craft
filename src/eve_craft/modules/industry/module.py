from __future__ import annotations

from eve_craft.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="industry",
        display_name="Industry",
        kind="feature",
        root_package="eve_craft.modules.industry",
        tab_object_name="Industry",
    )

