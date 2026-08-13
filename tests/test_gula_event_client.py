from datetime import datetime, timezone

import pytest

from app.contracts.device_observation import PendingDeviceObservation
from app.integration.gula_client import GulaClient


@pytest.mark.asyncio
async def test_pending_observation_is_published_as_safe_envelope(monkeypatch):
    client = GulaClient("https://gula.example", "lab-1", max_retries=1)
    sent = []

    async def fake_post(envelope):
        sent.append(envelope)
        return {"status": "staged"}

    monkeypatch.setattr(client, "_post_with_retry", fake_post)
    observation = PendingDeviceObservation(
        observation_id="obs-1",
        sample_id="sample-1",
        patient_id="patient-1",
        device_id="device-1",
        test_code="CBC",
        value=4.2,
        unit="10^9/L",
        reference_range="4-10",
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="pending_review",
        provenance="vendor:device:digest",
        idempotency_key="stable-observation-key",
    )

    response = await client.send_pending_observations([observation])

    assert response == [{"status": "staged"}]
    envelope = sent[0]
    assert envelope["event_type"] == "device.observation.pending"
    assert envelope["schema_version"] == 1
    assert envelope["idempotency_key"] == "stable-observation-key"
    assert envelope["payload"]["status"] == "pending_review"
    assert envelope["entity_id"] == "sample-1"


def test_pending_observation_envelope_is_stable_for_replay():
    client = GulaClient("https://gula.example", "lab-1")
    observation = PendingDeviceObservation(
        observation_id="obs-2",
        sample_id="sample-2",
        patient_id="patient-2",
        device_id="device-2",
        test_code="CRP",
        value=12.0,
        unit="mg/L",
        reference_range="0-5",
        observed_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status="pending_review",
        provenance="vendor:device:digest",
        idempotency_key="replay-key",
    )

    first = client.build_pending_observation_envelope(observation)
    second = client.build_pending_observation_envelope(observation)

    assert first == second
    assert first["correlation_id"] == first["event_id"]
    assert first["payload"]["status"] == "pending_review"
