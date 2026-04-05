# LabLink Core (GULA Integration Engine)

MVP foundation for a healthcare device middleware that ingests device output, parses ASTM-like records, normalizes results, and exposes API endpoints for integration workflows.

## MVP Scope (Implemented)

- Serial/TCP connector interfaces (MVP stubs)
- Basic ASTM-like parser for CBC-style lines
- Normalization into a unified result schema
- FastAPI service with:
  - `POST /ingest` to receive raw data
  - `GET /results` to inspect normalized output
  - `GET /logs` for basic ingestion/error logs
- Unit tests for parser and normalization

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Example Ingest Request

```bash
curl -X POST http://127.0.0.1:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "lab_id": "LAB001",
    "patient_id": "123",
    "device_id": "CBC-01",
    "raw_data": "|Hb|13.5|g/dL|"
  }'
```

## Next Steps

1. Replace connector stubs with actual `pyserial` and persistent TCP sockets.
2. Add PostgreSQL persistence (`devices`, `results`, `logs`).
3. Add outbound GULA REST client wiring and retry queue.
4. Add JWT auth and tenant isolation (`lab_id`).
5. Add HL7 parser in phase 2.
