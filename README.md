# LabLink Core (GULA Integration Engine)

Phase-1..7 baseline now includes ASTM pipeline, device emulator, registry, command system, and hardening primitives.

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
- **Mapping + patient fallback**
  - `TestMappingEngine` unifies aliases (e.g. `Hb`/`HGB` -> `HEMOGLOBIN`)
  - fallback patient matching from ingest request when patient record is missing
- **Production hardening primitives**
  - `RetryQueue` for failed upstream sends
  - offline queue persistence and audit trail in repository
- **Device emulator (Phase 4)**
  - `TCPDeviceEmulator` supporting ENQ/ACK, multi-result ASTM frames, optional bad checksum and disconnect simulation
- **API endpoints**
  - `POST /devices/register`
  - `GET /devices`
  - `GET /registry`
  - `POST /devices/{device_id}/command`
  - `POST /ingest`
  - `GET /results`, `GET /logs`, `GET /audit`, `GET /offline-queue`

## Run LabLink API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
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
