"""FHIR R4 protocol implementation for LabLink Platform."""
from __future__ import annotations

import json

from app.protocols.base import MessageDirection, MessageType, ProtocolInterface, ProtocolMessage


class FHIRProtocol(ProtocolInterface):
    """FHIR R4 resource-based protocol handler.

    Handles Observation, Patient, DiagnosticReport, and Bundle resources.
    """

    @property
    def protocol_name(self) -> str:
        return "FHIR"

    @property
    def protocol_version(self) -> str:
        return "R4"

    def parse(self, raw: bytes | str) -> ProtocolMessage:
        # Parse JSON FHIR resource
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text)
        resource_type = data.get("resourceType", "")
        msg_type = self._map_resource_type(resource_type)
        return ProtocolMessage(
            message_type=msg_type,
            direction=MessageDirection.INBOUND,
            protocol="FHIR",
            source=data.get("meta", {}).get("source", ""),
            payload=data,
            raw=raw.encode("utf-8") if isinstance(raw, str) else raw,
        )

    def serialize(self, message: ProtocolMessage) -> bytes:
        return json.dumps(message.payload, indent=2).encode("utf-8")

    def validate(self, raw: bytes | str) -> bool:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(text)
            return "resourceType" in data
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    def get_message_type(self, raw: bytes | str) -> MessageType | None:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            data = json.loads(text)
            return self._map_resource_type(data.get("resourceType", ""))
        except Exception:
            return None

    def create_observation(self, code: str, value: float, unit: str, patient_id: str) -> dict:
        """Create a FHIR Observation resource."""
        return {
            "resourceType": "Observation",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": code}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org"},
        }

    def create_patient(self, patient_id: str, family_name: str, given_name: str) -> dict:
        return {
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"family": family_name, "given": [given_name]}],
        }

    def create_diagnostic_report(self, patient_id: str, observations: list[dict]) -> dict:
        return {
            "resourceType": "DiagnosticReport",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0074", "code": "LAB"}]}],
            "subject": {"reference": f"Patient/{patient_id}"},
            "result": [{"reference": f"Observation/{o.get('id', '')}"} for o in observations],
        }

    def extract_observations(self, message: ProtocolMessage) -> list[dict]:
        payload = message.payload
        if payload.get("resourceType") == "Bundle":
            return [e["resource"] for e in payload.get("entry", []) if e.get("resource", {}).get("resourceType") == "Observation"]
        if payload.get("resourceType") == "Observation":
            return [payload]
        return []

    def _map_resource_type(self, resource_type: str) -> MessageType:
        mapping = {
            "Observation": MessageType.OBSERVATION,
            "Patient": MessageType.PATIENT,
            "DiagnosticReport": MessageType.OBSERVATION,
            "Bundle": MessageType.OBSERVATION,
            "ServiceRequest": MessageType.ORDER,
        }
        return mapping.get(resource_type, MessageType.OBSERVATION)
