from __future__ import annotations

from app.pipeline.normalizer import NormalizedResult, Normalizer
from app.pipeline.parser_engine import ParsedResult


def normalize_result(
    parsed: ParsedResult,
    *,
    patient_id: str,
    device_id: str,
    reference_range: str = "",
) -> NormalizedResult:
    return Normalizer().transform(
        parsed,
        patient_id=patient_id,
        device_id=device_id,
        reference_range=reference_range,
    )
