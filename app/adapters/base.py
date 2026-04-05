from __future__ import annotations

from abc import ABC, abstractmethod


class DeviceAdapter(ABC):
    """Vendor adapter layer for result-row normalization before core mapping."""

    @abstractmethod
    def transform_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        raise NotImplementedError
