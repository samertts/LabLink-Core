# GULA Device Observation Contract

## Purpose

LabLink-Core owns device communication, parsing, normalization, provenance, and durable delivery. GULA owns sample matching, clinical validation, authorization, and final result approval.

## Required observation fields

| Field | Requirement |
|---|---|
| `observation_id` | Deterministic identifier for the observation |
| `sample_id` | Required link to a verified sample; no orphan observation is accepted |
| `patient_id` | Identity supplied by the trusted matching workflow |
| `device_id` | Registered device identity |
| `test_code` | Normalized test identifier |
| `value` / `unit` | Parsed and normalized measurement |
| `observed_at` | Timezone-aware device/result timestamp |
| `provenance` | Source protocol, device, and message identity |
| `idempotency_key` | Stable hash preventing duplicate side effects |
| `status` | Always `pending_review` at this boundary |

## Safety rule

A device reading must never be exported as an approved clinical result. `build_pending_observation` intentionally converts a normalized result into `pending_review`. GULA must match the observation to the custody record and sample before any authorized reviewer can approve it.

## Idempotency and retry

The idempotency key is derived from the sample, device, test, value, unit, and UTC observation timestamp. Replaying the same device message must resolve to the same observation identity. Transport retries must be safe and must not create duplicate observations.

## Operational endpoint

`POST /ingest` now accepts `sample_id` explicitly. For backward-compatible device payloads, `barcode` can supply the sample identifier when it is a verified barcode. If neither is present, the service fails before processing the result.

Every accepted batch is persisted and returned as `pending_review` observations. The response includes `observation_id`, `sample_id`, provenance, and idempotency key; it never exposes a final clinical approval state.

## Integration boundary

LabLink-Core may emit raw, parsed, and normalized events for operational traceability. Only the pending observation contract crosses into GULA. The transport must preserve provenance, idempotency, and timestamps, and must return a hard failure when `sample_id` or provenance is absent.

## Future implementation steps

The next implementation batch should connect this contract to `ingest_service.py`, persist the pending state in `result_repository.py`, and update `gula_client.py` to send `sample_id`, `observation_id`, provenance, and status. The downstream GULA endpoint must reject `final` observations from this integration boundary.
