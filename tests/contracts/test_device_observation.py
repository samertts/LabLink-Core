from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.contracts.device_observation import build_pending_observation
from app.pipeline.normalizer import NormalizedResult


@pytest.fixture
def normalized_result() -> NormalizedResult:
    return NormalizedResult(
        patient_id="P-1",
        device_id="device-7",
        test_code="HB",
        test_name="Hemoglobin",
        value=13.2,
        unit="g/dL",
        reference_range="12-16",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="final",
    )


def test_device_result_is_pending_review_and_has_stable_idempotency(normalized_result):
    first = build_pending_observation(
        normalized_result,
        sample_id="S-100",
        provenance="astm:device-7:message-42",
    )
    second = build_pending_observation(
        normalized_result,
        sample_id="S-100",
        provenance="astm:device-7:message-42",
    )

    assert first.status == "pending_review"
    assert first.sample_id == "S-100"
    assert first.observation_id == second.observation_id
    assert first.idempotency_key == second.idempotency_key


def test_observation_requires_sample_and_provenance(normalized_result):
    with pytest.raises(ValueError, match="sample_id is required"):
        build_pending_observation(normalized_result, sample_id="", provenance="astm:1")

    with pytest.raises(ValueError, match="provenance is required"):
        build_pending_observation(normalized_result, sample_id="S-100", provenance="")


def test_naive_timestamp_is_rejected(normalized_result):
    naive = replace(normalized_result, timestamp=datetime(2026, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        build_pending_observation(naive, sample_id="S-100", provenance="astm:1")
