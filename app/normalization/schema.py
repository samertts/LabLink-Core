from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.parsers.astm_basic import ParsedResult

TEST_NAME_MAP = {
    "Hb": "Hemoglobin",
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


def normalize_result(
    parsed: ParsedResult,
    *,
    patient_id: str,
    device_id: str,
    reference_range: str = "",
) -> NormalizedResult:
    if not patient_id or not device_id:
        raise ValueError("patient_id and device_id are required")

    return NormalizedResult(
        patient_id=patient_id,
        device_id=device_id,
        test_code=parsed.test_code,
        test_name=TEST_NAME_MAP.get(parsed.test_code, parsed.test_code),
        value=parsed.value,
        unit=parsed.unit,
        reference_range=reference_range,
        timestamp=datetime.now(timezone.utc),
        status="final",
    )
