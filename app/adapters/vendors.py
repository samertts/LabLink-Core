from __future__ import annotations

from app.adapters.base import DeviceAdapter


class GenericASTMAdapter(DeviceAdapter):
    def transform_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        return rows


class SysmexAdapter(DeviceAdapter):
    def transform_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        for row in rows:
            row["test_code"] = row["test_code"].replace("HGB", "HB")
        return rows


class RocheAdapter(DeviceAdapter):
    def transform_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        for row in rows:
            row["unit"] = row["unit"].replace("10^9/L", "x10^9/L")
        return rows


class MindrayAdapter(DeviceAdapter):
    def transform_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        for row in rows:
            if row["patient_id"] == "UNKNOWN":
                row["patient_id"] = "UNMATCHED"
        return rows
