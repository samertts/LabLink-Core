from __future__ import annotations

from dataclasses import dataclass

from app.backup.engine import BackupEngine
from app.config.settings import AppSettings, get_settings
from app.core.alerting import AlertManager
from app.core.device_manager import DeviceManager
from app.core.device_onboarding import DeviceOnboardingDirector
from app.edge.sync_engine import SyncEngine
from app.events.base import EventBus
from app.integration.gula_client import GulaClient
from app.observability.metrics import MetricsCollector
from app.observability.tracing import Tracer
from app.pipeline.data_pipeline import DataPipeline
from app.pipeline.normalizer import Normalizer
from app.pipeline.parser_engine import ASTMParser
from app.plugins.manager import PluginManager
from app.services.device_service import DeviceService
from app.services.health_service import HealthService
from app.services.ingest_service import IngestService
from app.services.mode_service import ModeService
from app.services.query_service import QueryService
from app.storage.db import InMemoryDB
from app.storage.result_repository import LogRepository, ResultRepository
from app.tasks.worker import BackgroundWorker


@dataclass
class ServiceContainer:
    """Centralized dependency injection container for all application services.

    All dependencies are injected — no mutable global runtime state.
    """

    settings: AppSettings
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
    event_bus: EventBus
    metrics: MetricsCollector
    tracer: Tracer
    worker: BackgroundWorker
    plugin_manager: PluginManager
    backup_engine: BackupEngine


def create_service_container(settings: AppSettings | None = None) -> ServiceContainer:
    """Build and wire all services together via dependency injection."""
    if settings is None:
        settings = get_settings()

    db = InMemoryDB(db_path=settings.effective_db_path)
    repository = ResultRepository(db)
    log_repository = LogRepository(db)

    device_manager = DeviceManager()
    alerts = AlertManager()
    sync_engine = SyncEngine()
    onboarding_director = DeviceOnboardingDirector()

    event_bus = EventBus()
    metrics = MetricsCollector()
    tracer = Tracer()
    worker = BackgroundWorker(
        poll_interval=settings.worker_poll_interval_seconds,
        max_retries=settings.worker_max_retries,
    )

    gula_client = GulaClient(base_url=settings.gula_url, lab_id=settings.gula_lab_id)

    pipeline = DataPipeline(
        parser=ASTMParser(),
        normalizer=Normalizer(),
        gula_client=gula_client,
        result_repo=repository,
        log_repo=log_repository,
    )

    device_service = DeviceService(
        device_manager=device_manager,
        onboarding_director=onboarding_director,
        alerts=alerts,
        event_bus=event_bus,
        metrics=metrics,
    )
    ingest_service = IngestService(
        pipeline=pipeline,
        repository=repository,
        sync_engine=sync_engine,
        event_bus=event_bus,
        metrics=metrics,
    )
    health_service = HealthService(db=db, event_bus=event_bus, metrics=metrics)
    mode_service = ModeService()
    query_service = QueryService(repository=repository, alerts=alerts)

    plugin_manager = PluginManager(
        event_bus=event_bus,
        plugin_dirs=["plugins"],
        platform_version=settings.version,
    )

    backup_engine = BackupEngine(db_path=settings.effective_db_path)

    return ServiceContainer(
        settings=settings,
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
        event_bus=event_bus,
        metrics=metrics,
        tracer=tracer,
        worker=worker,
        plugin_manager=plugin_manager,
        backup_engine=backup_engine,
    )
