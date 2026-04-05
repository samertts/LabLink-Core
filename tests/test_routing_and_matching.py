from app.edge.agent import EdgeAgentBuffer
from app.pipeline.patient_matching import PatientMatcher
from app.pipeline.smart_router import SmartRoutingEngine


def test_patient_matcher_uses_barcode_when_patient_missing() -> None:
    matcher = PatientMatcher(barcode_map={"BC123": "PAT-77"})
    patient_id = matcher.resolve_patient_id(
        row_patient_id="UNKNOWN",
        fallback_patient_id="FALLBACK",
        barcode="BC123",
    )
    assert patient_id == "PAT-77"


def test_smart_router_policy_and_edge_buffer() -> None:
    router = SmartRoutingEngine()
    router.set_policy("DEV-1", "offline")

    decision = router.decide(device_id="DEV-1", results=[])
    assert decision.target == "offline"

    edge = EdgeAgentBuffer()
    edge.enqueue({"device_id": "DEV-1", "results": ["HEMOGLOBIN"]})
    assert edge.pending() == 1
    drained = edge.drain()
    assert len(drained) == 1
    assert edge.pending() == 0
