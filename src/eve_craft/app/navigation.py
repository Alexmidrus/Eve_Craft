from __future__ import annotations

from eve_craft.app.contracts import ModuleDescriptor


class MainTabNavigator:
    def __init__(self, tab_widget) -> None:
        self._tab_widget = tab_widget
        self._module_indexes: dict[str, int] = {}

    def register_module_tab(self, module: ModuleDescriptor) -> None:
        if module.tab_object_name is None:
            return

        tab_index = self._find_tab_index(module.tab_object_name)
        self._module_indexes[module.key] = tab_index

    def has_tab(self, module_key: str) -> bool:
        return module_key in self._module_indexes

    def tab_index(self, module_key: str) -> int:
        return self._module_indexes[module_key]

    def activate(self, module_key: str) -> None:
        self._tab_widget.setCurrentIndex(self.tab_index(module_key))

    def current_tab_name(self) -> str:
        current_widget = self._tab_widget.currentWidget()
        if current_widget is None:
            return ""

        return current_widget.objectName()

    def _find_tab_index(self, object_name: str) -> int:
        for index in range(self._tab_widget.count()):
            widget = self._tab_widget.widget(index)
            if widget is not None and widget.objectName() == object_name:
                return index

        raise LookupError(f"Tab with objectName='{object_name}' was not found in the UI.")

