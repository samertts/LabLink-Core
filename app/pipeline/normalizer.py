from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.pipeline.parser_engine import ParsedResult


TEST_NAME_MAP = {
    "HEMOGLOBIN": "Hemoglobin",
    "HB": "Hemoglobin",
    "HGB": "Hemoglobin",
}


@dataclass(slots=True)
class NormalizedResult:
    patient_id: str
    device_id: str
    test_code: str
    test_name: str
    value: float
    unit: str
    reference_range: str
    timestamp: datetime
    status: str


class Normalizer:
    def transform(
        self,
        data: ParsedResult,
        *,
        patient_id: str,
        device_id: str,
        reference_range: str = "",
    ) -> NormalizedResult:
        return NormalizedResult(
            patient_id=patient_id,
            device_id=device_id,
            test_code=data.test_code,
            test_name=TEST_NAME_MAP.get(data.test_code.upper(), data.test_code),
            value=data.value,
            unit=data.unit,
            reference_range=reference_range,
            timestamp=datetime.now(timezone.utc),
            status="final",
        )
