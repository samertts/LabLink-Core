from __future__ import annotations


class PatientMatcher:
    """Resolve patient IDs from ASTM row, barcode map, or fallback input."""

    def __init__(self, barcode_map: dict[str, str] | None = None) -> None:
        self.barcode_map = barcode_map or {}

    def resolve_patient_id(
        self,
        *,
        row_patient_id: str,
        fallback_patient_id: str,
        barcode: str | None = None,
    ) -> str:
        if row_patient_id and row_patient_id not in {"UNKNOWN", "UNMATCHED"}:
            return row_patient_id
        if barcode and barcode in self.barcode_map:
            return self.barcode_map[barcode]
        return fallback_patient_id
