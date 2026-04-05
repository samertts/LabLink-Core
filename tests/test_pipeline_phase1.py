import asyncio

from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ParserEngine
from app.storage.result_repository import LogRepository, ResultRepository


def test_parser_engine_handles_fragmented_stream() -> None:
    parser = ParserEngine()
    assert parser.feed("|Hb|13") == []
    parsed = parser.feed(".5|g/dL|\n")
    assert len(parsed) == 1
    assert parsed[0].test_code == "Hb"
    assert parsed[0].value == 13.5


def test_data_pipeline_processes_chunk_to_result() -> None:
    pipeline = DataPipeline(
        parser=ParserEngine(),
        normalizer=Normalizer(),
        result_repo=ResultRepository(),
        log_repo=LogRepository(),
    )

    asyncio.run(pipeline.process_chunk("|Hb|13.5|g/dL|\n", patient_id="P-1", device_id="CBC-01"))

    assert len(pipeline.result_repo.list()) == 1
    assert pipeline.result_repo.list()[0].test_name == "Hemoglobin"
    assert len(pipeline.log_repo.list()) == 1
