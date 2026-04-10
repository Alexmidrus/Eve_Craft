from __future__ import annotations

from iph2.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="market",
        display_name="Market",
        kind="feature",
        root_package="iph2.modules.market",
        tab_object_name="Market",
    )
