# LabLink Core (GULA Integration Engine)

Phase-1..7 baseline now includes ASTM pipeline, device emulator, registry, adapter layer, command system, smart routing, patient matching, edge/offline buffering, and sync/security primitives.

## Implemented

- **Connectors + Handshake**
  - `BaseConnector` with `send_command`
  - `SerialConnector` / `TCPConnector` with ENQ/ACK/EOT handling and reconnect behavior
- **Multi-device orchestration**
  - `ConnectionPool` with `send_to` + `broadcast`
  - `DeviceManager` with registry-backed device lifecycle + command dispatch
  - `DeviceRegistry` stores device metadata (`device_id`, vendor, protocol, connection)
- **ASTM protocol engine**
  - `ASTMBuffer` (STX/ETX framing + fragmentation)
  - checksum calc/validation
  - parser for `H/P/R/L` records
  - message builder to associate results with active patient
- **Adapter layer (vendor-specific)**
  - `AdapterRegistry`
  - `SysmexAdapter`, `RocheAdapter`, `MindrayAdapter`, plus generic adapter
- **Patient matching + mapping**
  - `PatientMatcher` resolves patient IDs from ASTM, barcode map, or fallback
  - `TestMappingEngine` unifies aliases (e.g. `Hb`/`HGB` -> `HEMOGLOBIN`)
- **Smart routing + edge mode**
  - `SmartRoutingEngine` routes per device policy (`gula`/`offline`/`both`)
  - `EdgeAgentBuffer` stores data in offline/branch mode and supports later sync
  - `SyncEngine` stages and syncs edge payloads with retry-friendly behavior
- **Production hardening + security**
  - `RetryQueue` for failed upstream sends
  - offline queue persistence and audit trail in repository
  - `AlertManager` for operational alerts
  - API key protection via `x-api-key` header (env: `LABLINK_API_KEY`)
  - deployment modes: `local_only`, `hybrid`, `cloud_only`
- **Device emulator (Phase 4)**
  - `TCPDeviceEmulator` supporting ENQ/ACK, multi-result ASTM frames, bad checksum mode, disconnect simulation, and multi-patient streams
- **Device onboarding director (new)**
  - Identity scoring from hardware fingerprint (VID/PID/manufacturer/model)
  - Driver candidate discovery per OS (Windows/Linux)
  - Installation plan generator with secure validation steps
  - Wired/wireless transport recommendation for high-speed operation

- **API endpoints**
  - `POST /devices/register`
  - `GET /devices`
  - `GET /registry`
  - `POST /devices/onboarding/scan`
  - `POST /devices/{device_id}/command`
  - `POST /devices/{device_id}/routing`
  - `POST /mode`, `GET /mode`
  - `POST /ingest` (supports optional `vendor` and `barcode`)
  - `POST /edge/sync`
  - `GET /alerts`
  - `GET /results`, `GET /logs`, `GET /audit`, `GET /offline-queue`

## Run LabLink API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
export LABLINK_API_KEY=lablink-dev-key
uvicorn app.main:app --reload
```

## Run Device Emulator

```bash
python -m app.emulator.tcp_device_emulator
```

## Test

```bash
pytest -q
```


## Project Manager Blueprint

See `docs/PROJECT_DIRECTOR_PLAN.md` for the world-class rollout strategy and research references.
