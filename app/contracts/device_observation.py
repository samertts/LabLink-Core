"""Safe boundary between device output and clinical result approval."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from app.pipeline.normalizer import NormalizedResult


@dataclass(frozen=True, slots=True)
class PendingDeviceObservation:
    observation_id: str
    sample_id: str
    patient_id: str
    device_id: str
    test_code: str
    value: float
    unit: str
    reference_range: str
    observed_at: datetime
    status: str
    provenance: str
    idempotency_key: str


def build_pending_observation(
    result: NormalizedResult,
    *,
    sample_id: str,
    provenance: str,
) -> PendingDeviceObservation:
    """Build an unapproved observation; approval is owned by the clinical system."""
    if not sample_id.strip():
        raise ValueError("sample_id is required")
    if not provenance.strip():
        raise ValueError("provenance is required")
    if result.status.lower() not in {"final", "pending", "pending_review"}:
        raise ValueError(f"Unsupported normalized result status: {result.status}")
    if result.timestamp.tzinfo is None:
        raise ValueError("result.timestamp must be timezone-aware")

    identity = "|".join(
        (
            sample_id.strip(),
            result.device_id.strip(),
            result.test_code.strip().upper(),
            str(result.value),
            result.unit.strip(),
            result.timestamp.astimezone(timezone.utc).isoformat(),
        )
    )
    idempotency_key = sha256(identity.encode("utf-8")).hexdigest()
    return PendingDeviceObservation(
        observation_id=f"obs-{idempotency_key[:24]}",
        sample_id=sample_id.strip(),
        patient_id=result.patient_id,
        device_id=result.device_id,
        test_code=result.test_code,
        value=result.value,
        unit=result.unit,
        reference_range=result.reference_range,
        observed_at=result.timestamp.astimezone(timezone.utc),
        status="pending_review",
        provenance=provenance.strip(),
        idempotency_key=idempotency_key,
    )
