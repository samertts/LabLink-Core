from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.alerting import AlertManager
from app.core.device_manager import DeviceManager
from app.core.device_onboarding import DeviceOnboardingDirector
from app.edge.sync_engine import SyncEngine
from app.integration.gula_client import GulaClient
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ASTMParser
from app.services.device_service import DeviceService
from app.services.health_service import HealthService
from app.services.ingest_service import IngestService
from app.services.mode_service import ModeService
from app.services.query_service import QueryService
from app.settings.paths import DATA_DIR
from app.storage.db import InMemoryDB
from app.storage.result_repository import LogRepository, ResultRepository


@dataclass
class ServiceContainer:
    """Centralized dependency injection container for all application services."""

    db: InMemoryDB
    repository: ResultRepository
    log_repository: LogRepository
    device_service: DeviceService
    ingest_service: IngestService
    health_service: HealthService
    mode_service: ModeService
    query_service: QueryService
    pipeline: DataPipeline
    alerts: AlertManager


def create_service_container() -> ServiceContainer:
    """Build and wire all services together."""
    db = InMemoryDB(db_path=str(DATA_DIR / "lablink.db"))
    repository = ResultRepository(db)
    log_repository = LogRepository(db)

    device_manager = DeviceManager()
    alerts = AlertManager()
    sync_engine = SyncEngine()
    onboarding_director = DeviceOnboardingDirector()

    gula_url = os.getenv("LABLINK_GULA_URL", "http://gula.local")
    gula_lab_id = os.getenv("LABLINK_GULA_LAB_ID", "LAB001")

    pipeline = DataPipeline(
        parser=ASTMParser(),
        normalizer=Normalizer(),
        gula_client=GulaClient(base_url=gula_url, lab_id=gula_lab_id),
        result_repo=repository,
        log_repo=log_repository,
    )

    device_service = DeviceService(
        device_manager=device_manager,
        onboarding_director=onboarding_director,
        alerts=alerts,
    )
    ingest_service = IngestService(
        pipeline=pipeline,
        repository=repository,
        sync_engine=sync_engine,
    )
    health_service = HealthService(db=db)
    mode_service = ModeService()
    query_service = QueryService(repository=repository, alerts=alerts)

    return ServiceContainer(
        db=db,
        repository=repository,
        log_repository=log_repository,
        device_service=device_service,
        ingest_service=ingest_service,
        health_service=health_service,
        mode_service=mode_service,
        query_service=query_service,
        pipeline=pipeline,
        alerts=alerts,
    )
