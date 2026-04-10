from __future__ import annotations

from iph2.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="industry",
        display_name="Industry",
        kind="feature",
        root_package="iph2.modules.industry",
        tab_object_name="Industry",
    )
