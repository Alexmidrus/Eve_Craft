from __future__ import annotations

from eve_craft.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="market",
        display_name="Market",
        kind="feature",
        root_package="eve_craft.modules.market",
        tab_object_name="tabMarket",
    )

