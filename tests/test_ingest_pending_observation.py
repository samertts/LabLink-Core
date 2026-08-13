from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.modes import CommunicationMode
from app.pipeline.normalizer import NormalizedResult
from app.services.ingest_service import IngestService


class FakePipeline:
    def __init__(self, result: NormalizedResult):
        self.result = result
        self.router = SimpleNamespace(set_policy=lambda *_args: None)
        self.retry_queue = SimpleNamespace(size=lambda: 0)

    async def process_chunk(self, **_kwargs):
        return [self.result]


class FakeRepository:
    def __init__(self):
        self.logs = []
        self.saved = []

    def save_log(self, **payload):
        self.logs.append(payload)

    def save_results(self, results):
        self.saved.extend(results)


class FakeSyncEngine:
    def stage(self, **_kwargs):
        raise AssertionError("retry queue should be empty in this test")


@pytest.mark.asyncio
async def test_ingest_returns_pending_observation_linked_to_sample():
    result = NormalizedResult(
        patient_id="P-1",
        device_id="device-7",
        test_code="HB",
        test_name="Hemoglobin",
        value=13.2,
        unit="g/dL",
        reference_range="12-16",
        timestamp=datetime.now(timezone.utc),
        status="final",
    )
    repository = FakeRepository()
    service = IngestService(FakePipeline(result), repository, FakeSyncEngine())

    response = await service.ingest(
        device_id="device-7",
        patient_id="P-1",
        sample_id="S-100",
        chunk="ASTM|message-1",
        vendor="vendor-a",
        current_mode=CommunicationMode.HYBRID,
    )

    assert response.status == "ok"
    assert response.processed == 1
    assert response.results[0].status == "pending_review"
    assert response.results[0].sample_id == "S-100"
    assert response.results[0].provenance.startswith("vendor-a:device-7:")
    assert repository.saved[0].status == "pending_review"


@pytest.mark.asyncio
async def test_ingest_rejects_orphan_device_result():
    result = NormalizedResult(
        patient_id="P-1",
        device_id="device-7",
        test_code="HB",
        test_name="Hemoglobin",
        value=13.2,
        unit="g/dL",
        reference_range="12-16",
        timestamp=datetime.now(timezone.utc),
        status="final",
    )
    service = IngestService(FakePipeline(result), FakeRepository(), FakeSyncEngine())

    with pytest.raises(ValueError, match="sample_id or barcode is required"):
        await service.ingest(
            device_id="device-7",
            patient_id="P-1",
            chunk="ASTM|message-1",
            current_mode=CommunicationMode.HYBRID,
        )
