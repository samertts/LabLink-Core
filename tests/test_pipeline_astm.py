import asyncio

from app.integration.gula_client import GulaClient
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ASTMParser, calculate_checksum


class FakeGulaClient(GulaClient):
    def __init__(self) -> None:
        super().__init__(base_url="http://example.invalid", lab_id="LAB001")
        self.sent_batches = []

    async def send_results(self, results):  # type: ignore[override]
        self.sent_batches.append(results)
        return {"status": "ok"}


def build_frame(payload_text: str) -> bytes:
    payload = payload_text.encode("ascii")
    checksum = calculate_checksum(payload).encode("ascii")
    return b"\x02" + payload + b"\x03" + checksum + b"\r\n"


def test_pipeline_processes_real_astm_frame() -> None:
    gula = FakeGulaClient()
    pipeline = DataPipeline(parser=ASTMParser(), normalizer=Normalizer(), gula_client=gula)

    payload = "1H|\\^&|||Device|||||P|1\r2P|1||12345||Doe^John\r3R|1|^^^Hb|13.5|g/dL\r"
    frame = build_frame(payload)

    results = asyncio.run(
        pipeline.process_chunk(device_id="CBC-01", fallback_patient_id="FALLBACK", chunk=frame)
    )

    assert len(results) == 1
    assert results[0].patient_id == "12345"
    assert results[0].test_code == "Hb"
    assert len(gula.sent_batches) == 1
