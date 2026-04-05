from __future__ import annotations

from app.adapters.base import DeviceAdapter
from app.adapters.vendors import GenericASTMAdapter, MindrayAdapter, RocheAdapter, SysmexAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, DeviceAdapter] = {
            "GENERIC": GenericASTMAdapter(),
            "SYSMEX": SysmexAdapter(),
            "ROCHE": RocheAdapter(),
            "MINDRAY": MindrayAdapter(),
        }

    def resolve(self, vendor: str | None) -> DeviceAdapter:
        if not vendor:
            return self._adapters["GENERIC"]
        return self._adapters.get(vendor.upper(), self._adapters["GENERIC"])
