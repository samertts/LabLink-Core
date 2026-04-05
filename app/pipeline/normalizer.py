from __future__ import annotations

from app.normalization.schema import NormalizedResult, normalize_result
from app.parsers.astm_basic import ParsedResult


class Normalizer:
    def transform(self, parsed: ParsedResult, *, patient_id: str, device_id: str) -> NormalizedResult:
        return normalize_result(parsed, patient_id=patient_id, device_id=device_id)
