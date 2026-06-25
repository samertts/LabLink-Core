# Changelog

## 1.0.0 - 2026-05-25
- Added production desktop entrypoint and PySide6 desktop shell.
- Added startup validation, compatibility checks, and automated runtime repair.
- Added structured logging with crash logs under `storage/logs`.
- Added Windows PyInstaller + Inno Setup build pipeline via GitHub Actions.

## 1.3.0 - 2026-06-25

### Phase 1 — Event Bus
- **Production-grade publish/subscribe Event Bus** (`app/events/`).
  - Thread-safe with `threading.Lock`.
  - Async-compatible via `publish_async()`.
  - Typed events with `EventMetadata` (event_id, timestamp, correlation_id, source, version).
  - Event replay support via `get_history()`.
  - Interceptor pipeline for event transformation.
  - Wildcard subscription (`*`) for cross-cutting concerns.
  - 12 domain events: DeviceConnected, DeviceDisconnected, DeviceRegistered, ResultReceived, ResultValidated, ResultNormalized, ResultStored, ResultExported, AlertRaised, SyncStarted, SyncCompleted, HealthChanged.

### Phase 2 — Domain Events
- Services now emit events through the EventBus on key operations.
- DeviceService publishes DeviceRegistered, DeviceConnected, AlertRaised on device operations.
- IngestService publishes ResultReceived, ResultNormalized, ResultStored, SyncStarted, SyncCompleted.
- HealthService publishes HealthChanged on health checks.

### Phase 3 — Dependency Injection
- Replaced global mutable state with constructor-injected dependencies.
- `ServiceContainer` now accepts `AppSettings` and passes all dependencies to services.
- All services accept optional `EventBus` and `MetricsCollector` via constructors.
- FastAPI `lifespan` replaces deprecated `on_event` handlers.

### Phase 4 — Configuration System
- Centralized typed settings (`app/config/settings.py`) using Pydantic `BaseSettings`.
- Supports environment variables (prefixed `LABLINK_`), `.env` files, and defaults.
- Settings: app_name, version, debug, environment, host, port, api_key, cors_origins, rate_limit, gula_url/lab_id, db_path, data_dir, log_level, worker settings, health_check_interval.
- `get_settings()` singleton for application-wide access.

### Phase 5 — Repository Abstraction
- Abstract interfaces (`app/storage/repositories.py`): `ResultRepositoryProtocol`, `LogRepositoryProtocol`, `AuditRepository`, `OfflineQueueRepository`.
- `ResultRepository` now implements all four protocols.
- `LogRepository` implements `LogRepositoryProtocol`.
- Business logic depends on interfaces; implementations are swappable for PostgreSQL, etc.

### Phase 6 — Background Tasks
- Thread-safe `BackgroundWorker` (`app/tasks/worker.py`).
- Task queue with priority processing.
- Handler registration by task name.
- Periodic task scheduling.
- Automatic retry with configurable max retries.
- Task result tracking with status, duration, error capture.
- Integrated into `ServiceContainer` with configurable poll interval.

### Phase 7 — Observability Foundation
- `MetricsCollector` (`app/observability/metrics.py`): counters, gauges, histograms with tag support and percentile stats.
- `Tracer` (`app/observability/tracing.py`): in-process distributed tracing with spans, attributes, events, and trace history.
- New API endpoints: `GET /metrics`, `GET /traces`.
- Ready for future Prometheus/OpenTelemetry integration.

### Tests
- Added 52 new tests (137 total, up from 85).
- Tests cover: EventBus (12 tests), Domain Events (1), Config (9), Observability (9), Tasks (8), Repositories (9), plus integration with existing services.

## 1.2.0 - 2026-06-25

### Architecture
- **Service Layer Extraction**: Refactored monolithic `app/main.py` (440 lines) into clean service layer following SOLID and Clean Architecture principles.
  - `app/services/device_service.py`: Device registration, listing, command sending, onboarding, and scanning.
  - `app/services/ingest_service.py`: Data ingestion pipeline orchestration, retry queue draining, edge sync.
  - `app/services/health_service.py`: Health check and readiness probe logic.
  - `app/services/mode_service.py`: Thread-safe communication mode management (replaces `_ThreadSafeMode`).
  - `app/services/query_service.py`: Paginated read access to all persisted data (results, logs, audit, alerts, offline queue).
  - `app/services/service_container.py`: Centralized dependency injection container wiring all services together.
- `app/main.py` is now a thin HTTP routing layer (~300 lines) delegating to services.
- All business logic extracted from API handlers into independently testable service classes.

### Tests
- Added 30 new service-layer unit tests across `tests/test_services.py` and `tests/test_services_extended.py`.
- Total test count: 85 tests (up from 55).
- Tests cover: DeviceService (register, list, command, scan, onboarding), HealthService, ModeService, QueryService (pagination, audit events).

## 1.1.0 - 2026-06-25

### Security (Critical)
- Removed hardcoded API key default. Now generates a secure random key when `LABINK_API_KEY` is not set, with a runtime warning.
- API key comparison now uses `secrets.compare_digest` to prevent timing attacks.
- Exception messages no longer exposed to API clients; detailed errors logged server-side only.
- Added input validation on device command endpoint (length, character restrictions).
- Added CORS middleware with explicit origin allowlist.
- Added rate limiting middleware (sliding window, 200 requests/minute per IP).

### Architecture
- Added `__init__.py` files to all packages for proper Python package recognition.
- Added `app/middleware/` package for HTTP middleware components.
- Renamed `app/logging/` to `app/log_config/` to avoid shadowing Python's `logging` module.
- Thread-safe global mode state via `_ThreadSafeMode` class with lock.
- Thread-safe `AlertManager` with bounded storage and max alert limit.
- Thread-safe `TCPConnector` socket reference via `_socket_lock`.
- Added `ASTMMessageBuilder.reset()` method to prevent state leakage between frames.
- SQLite-backed persistent storage replaces pure in-memory lists.
- Graceful shutdown handler closes DB, GULA client, and disconnects devices.
- ResultRepository and LogRepository now share the same DB instance.

### Reliability
- Unsafe `float()` conversion in data pipeline now catches `ValueError`/`TypeError` and skips invalid values with logging.
- Retry queue now properly dequeues items after processing instead of re-enumerating forever.
- GULA client now uses connection pooling (`httpx.AsyncClient` reuse) and retry with exponential backoff.
- Desktop server now detects port conflicts before attempting to start.
- Health check endpoint now verifies database integrity.
- Unbounded memory growth fixed: AlertManager capped at 1000 entries, repositories use SQLite with truncation.

### Dependencies
- Added `pyserial>=3.5` to both `pyproject.toml` and `requirements.txt`.
- Version aligned to 1.0.0 across all files (`pyproject.toml`, `VERSION`, `installer/setup.iss`, `app/main.py`).
- `pyproject.toml` now includes full project metadata (authors, classifiers, URLs, license).
- Added optional dependency groups: `dev`, `desktop`, `build`.

### API
- All list endpoints (`/alerts`, `/results`, `/logs`, `/audit`, `/offline-queue`) now support `limit` and `offset` query parameters for pagination.
- Health endpoint returns version and dependency checks.
- `POST /devices/{device_id}/command` returns 404 when device not found instead of generic error.

### Configuration
- GULA URL and lab ID now configurable via `LABLINK_GULA_URL` and `LABLINK_GULA_LAB_ID` environment variables.

### Developer Experience
- Added `ruff` linting configuration to `pyproject.toml`.
- Added `mypy` type checking configuration to `pyproject.toml`.
- Added `pytest-cov` for code coverage reporting.
- Added `tests/conftest.py` with shared test fixtures (FakeConnector, DummyDeviceManager, InMemoryDB fixtures).
- CI/CD now tests on Ubuntu and Windows across Python 3.10-3.12 with coverage reporting.

### Installer
- Inno Setup now requires admin privileges with override dialog.
