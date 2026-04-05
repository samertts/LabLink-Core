# LabLink Core (GULA Integration Engine)

Phase-1 implementation of the **Device Connector Engine** (العمود الفقري):
- resilient connector abstractions,
- continuous stream ingestion,
- fragmented ASTM record handling,
- normalization and pipeline processing,
- FastAPI ingestion APIs.

## Implemented Architecture

```text
app/
├── app.py
├── core/
│   ├── connection_pool.py
│   └── device_manager.py
├── connectors/
│   └── base.py
├── integration/
│   └── gula_client.py
├── pipeline/
│   ├── data_pipeline.py
│   ├── normalizer.py
│   └── parser_engine.py
├── storage/
│   ├── db.py
│   └── result_repository.py
└── main.py
```

## Key Phase-1 Capabilities

- **Connector base layer** with lifecycle callbacks (`on_data`, `on_disconnect`).
- **Serial connector** (real pyserial implementation, lazy import) with optional trigger command loop.
- **TCP connector** with persistent read loop and disconnect propagation.
- **ConnectionPool** with automatic reconnect attempts after disconnects.
- **DeviceManager** for creating connectors from typed device config.
- **ParserEngine** with buffering + delimiter-aware stream processing and state-machine field parsing.
- **DataPipeline** that logs raw chunks, parses records, normalizes output, and can push to GULA.
- **In-memory repositories** for results/logs during phase-1.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Ingest Example (fragment-safe)

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "lab_id": "LAB001",
    "patient_id": "123",
    "device_id": "CBC-01",
    "raw_data": "|Hb|13.5|g/dL|\n"
  }'
```

## Next Steps

1. Add PostgreSQL persistence behind repository interfaces.
2. Add outbound retry queue for GULA failures.
3. Extend parser engine for richer ASTM/HL7 messages.
4. Add tenant-aware auth and command channel back to devices.
