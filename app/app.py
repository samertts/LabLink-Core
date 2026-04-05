from __future__ import annotations

from app.core.device_manager import DeviceManager
from app.integration.gula_client import GulaClient
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ASTMParser


def build_runtime() -> tuple[DeviceManager, DataPipeline]:
    manager = DeviceManager()
    pipeline = DataPipeline(
        parser=ASTMParser(),
        normalizer=Normalizer(),
        gula_client=GulaClient(base_url="http://gula.local", lab_id="LAB001"),
    )
    return manager, pipeline
