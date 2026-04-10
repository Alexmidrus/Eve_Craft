from __future__ import annotations

from iph2.app.contracts import ModuleDescriptor


def build_module() -> ModuleDescriptor:
    return ModuleDescriptor(
        key="service",
        display_name="Service",
        kind="service",
        root_package="iph2.platform",
    )
