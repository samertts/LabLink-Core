# Changelog

## 1.0.0 - 2026-05-25
- Added production desktop entrypoint and PySide6 desktop shell.
- Added startup validation, compatibility checks, and automated runtime repair.
- Added structured logging with crash logs under `storage/logs`.
- Added Windows PyInstaller + Inno Setup build pipeline via GitHub Actions.

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
