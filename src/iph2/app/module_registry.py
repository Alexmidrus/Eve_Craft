from __future__ import annotations

from collections.abc import Iterable

from iph2.app.contracts import ModuleDescriptor
from iph2.modules.industry.module import build_module as build_industry_module
from iph2.modules.market.module import build_module as build_market_module
from iph2.platform.module import build_module as build_service_module


class ModuleRegistry:
    def __init__(self, modules: Iterable[ModuleDescriptor]) -> None:
        ordered_modules = tuple(modules)
        modules_by_key = {module.key: module for module in ordered_modules}

        if len(ordered_modules) != len(modules_by_key):
            raise ValueError("Module keys must be unique.")

        self._ordered_modules = ordered_modules
        self._modules_by_key = modules_by_key

    def all(self) -> tuple[ModuleDescriptor, ...]:
        return self._ordered_modules

    def feature_modules(self) -> tuple[ModuleDescriptor, ...]:
        return tuple(module for module in self._ordered_modules if module.kind == "feature")

    def service_modules(self) -> tuple[ModuleDescriptor, ...]:
        return tuple(module for module in self._ordered_modules if module.kind == "service")

    def get(self, key: str) -> ModuleDescriptor:
        return self._modules_by_key[key]


def build_default_registry() -> ModuleRegistry:
    return ModuleRegistry(
        modules=(
            build_industry_module(),
            build_market_module(),
            build_service_module(),
        )
    )
