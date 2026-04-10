from __future__ import annotations

from eve_craft.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="service",
        display_name="Service",
        kind="service",
        root_package="eve_craft.platform",
    )

