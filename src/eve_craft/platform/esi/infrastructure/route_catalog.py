from __future__ import annotations

from collections.abc import Iterable

from eve_craft.platform.esi.domain.models import EsiOperationDescriptor


class EsiRouteCatalog:
    def __init__(self, operations: Iterable[EsiOperationDescriptor] = ()) -> None:
        self._operations: dict[str, EsiOperationDescriptor] = {}
        for operation in operations:
            self.register(operation)

    def register(self, operation: EsiOperationDescriptor) -> EsiOperationDescriptor:
        self._operations[operation.key] = operation
        return operation

    def get(self, key: str) -> EsiOperationDescriptor:
        return self._operations[key]

    def all(self) -> tuple[EsiOperationDescriptor, ...]:
        return tuple(self._operations.values())

