from __future__ import annotations

import asyncio
import logging

from app.core.connection_pool import ConnectionPool
from app.core.device_manager import DeviceConfig, DeviceManager
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ParserEngine
from app.storage.result_repository import LogRepository, ResultRepository

logger = logging.getLogger("lablink.runtime")


async def run() -> None:
    result_repo = ResultRepository()
    log_repo = LogRepository()
    pipeline = DataPipeline(
        parser=ParserEngine(),
        normalizer=Normalizer(),
        result_repo=result_repo,
        log_repo=log_repo,
    )

    manager = DeviceManager(pool=ConnectionPool())

    # Example device; replace with real deployment config.
    # connector = manager.add_device(DeviceConfig(device_id="CBC-01", connection_type="serial", path="/dev/ttyUSB0"))
    # connector.on_data(lambda chunk: asyncio.create_task(pipeline.process_chunk(chunk, patient_id="UNKNOWN", device_id="CBC-01")))

    logger.info("LabLink runtime initialized", extra={"results": len(result_repo.list())})
    await asyncio.sleep(0)


if __name__ == "__main__":
    asyncio.run(run())
