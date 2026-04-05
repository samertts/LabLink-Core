# LabLink Core (GULA Integration Engine)

Phase-1/2/3 backbone with real ASTM framing/parsing and protocol basics (checksum + handshake handling).

## Implemented

- **Connectors**
  - `BaseConnector`
  - `SerialConnector` with ASTM handshake behavior for control bytes (`ENQ` => `ACK`, `EOT` handling)
  - `TCPConnector` with reconnect loop
- **Device orchestration**
  - `ConnectionPool`
  - `DeviceManager`
- **ASTM protocol engine**
  - `ASTMBuffer` (byte buffering, STX/ETX extraction, fragmentation support)
  - Checksum calculation + validation
  - `ASTMParser` for `H`, `P`, `R`, `L` records
  - `ASTMMessageBuilder` to bind results to current patient across records
- **Data pipeline**
  - `DataPipeline` validates checksum, parses multi-line frames, builds results, normalizes, and sends to GULA
- **API**
  - `POST /ingest` receives raw ASTM chunks (including control chars)
  - `GET /results`
  - `GET /logs`

## Project structure

```text
app/
  app.py
  main.py
  core/
    connection_pool.py
    device_manager.py
  connectors/
    base.py
  pipeline/
    data_pipeline.py
    parser_engine.py
    normalizer.py
  integration/
    gula_client.py
  storage/
    db.py
    result_repository.py
```

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Test

```bash
pytest -q
```
