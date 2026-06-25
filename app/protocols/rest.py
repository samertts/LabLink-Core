"""REST/HTTP protocol implementation for LabLink Platform."""
from __future__ import annotations

import json

from app.protocols.base import MessageDirection, MessageType, ProtocolInterface, ProtocolMessage


class RESTProtocol(ProtocolInterface):
    """REST/HTTP JSON protocol handler.

    For receiving lab results via REST API endpoints.
    """

    @property
    def protocol_name(self) -> str:
        return "REST"

    def parse(self, raw: bytes | str) -> ProtocolMessage:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        data = json.loads(text) if text.strip() else {}
        msg_type = self._infer_type(data)
        return ProtocolMessage(
            message_type=msg_type,
            direction=MessageDirection.INBOUND,
            protocol="REST",
            payload=data,
            raw=raw.encode("utf-8") if isinstance(raw, str) else raw,
        )

    def serialize(self, message: ProtocolMessage) -> bytes:
        return json.dumps(message.payload, indent=2).encode("utf-8")

    def validate(self, raw: bytes | str) -> bool:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            json.loads(text)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False

    def create_result_payload(self, patient_id: str, results: list[dict]) -> dict:
        return {"patient_id": patient_id, "results": results, "format": "lablink"}

    def _infer_type(self, data: dict) -> MessageType:
        if "results" in data:
            return MessageType.OBSERVATION
        if "patient_id" in data and "order_id" in data:
            return MessageType.ORDER
        return MessageType.OBSERVATION
