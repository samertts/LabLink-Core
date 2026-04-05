from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ParsedResult


def test_normalize_result_maps_hb_to_hemoglobin() -> None:
    parsed = ParsedResult(test_code="Hb", value=13.5, unit="g/dL")
    normalized = Normalizer().transform(parsed, patient_id="P1", device_id="CBC-01")

    assert normalized.test_name == "Hemoglobin"
    assert normalized.status == "final"
