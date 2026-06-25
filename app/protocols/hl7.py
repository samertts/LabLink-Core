"""HL7 v2.x protocol implementation.

Supports parsing and generating HL7 v2.x messages including
ADT (A01-A08), ORM, ORU, and ACK message types.
"""

from __future__ import annotations

import re
from typing import Any

from app.protocols.base import MessageDirection, MessageType, ProtocolInterface, ProtocolMessage


class HL7Protocol(ProtocolInterface):
    """HL7 v2.x message handler.

    Handles pipe-delimited HL7 messages with MSH, PID, OBR, OBX,
    and other standard segments.
    """

    @property
    def protocol_name(self) -> str:
        return "HL7"

    @property
    def protocol_version(self) -> str:
        return "2.5.1"

    def parse(self, raw: bytes | str) -> ProtocolMessage:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        segments = self._split_segments(text)
        if not segments:
            raise ValueError("Empty HL7 message")

        header = segments[0]
        fields = header.split("|")
        if len(fields) < 9 or fields[0] != "MSH":
            raise ValueError("Invalid HL7 message: missing MSH segment")

        msg_type = self._determine_type(segments)
        payload = self._segments_to_dict(segments)

        return ProtocolMessage(
            message_type=msg_type,
            direction=MessageDirection.INBOUND,
            protocol="HL7",
            source=payload.get("sending_application", ""),
            destination=payload.get("receiving_application", ""),
            payload=payload,
            raw=raw.encode("utf-8") if isinstance(raw, str) else raw,
        )

    def serialize(self, message: ProtocolMessage) -> bytes:
        if message.payload.get("_raw_hl7"):
            return message.payload["_raw_hl7"].encode("utf-8")

        lines = ["MSH|^~\\&|"]
        if message.message_type == MessageType.ACKNOWLEDGMENT:
            accepted = message.payload.get("accepted", True)
            control_id = message.payload.get("control_id", "")
            lines.append(f"MSA|{'AA' if accepted else 'AE'}|{control_id}|")
        return "\r".join(lines).encode("utf-8")

    def validate(self, raw: bytes | str) -> bool:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        try:
            segments = self._split_segments(text)
            if not segments:
                return False
            return segments[0].startswith("MSH|")
        except Exception:
            return False

    def get_message_type(self, raw: bytes | str) -> MessageType | None:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        try:
            segments = self._split_segments(text)
            return self._determine_type(segments)
        except Exception:
            return None

    def get_sequence_number(self, raw: bytes | str) -> str | None:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        match = re.search(r"MSH\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|([^\|]*)", text)
        return match.group(1) if match else None

    def parse_obx_segments(self, message: ProtocolMessage) -> list[dict[str, Any]]:
        """Extract OBX (observation) segments from a parsed message."""
        results = []
        segments = message.payload.get("_segments", [])
        for seg in segments:
            if isinstance(seg, str) and seg.startswith("OBX|"):
                fields = seg.split("|")
                if len(fields) >= 5:
                    set_num = fields[1]
                    value_type = fields[2]
                    identifier = fields[3]
                    value = fields[5] if len(fields) > 5 else ""
                    unit = fields[6] if len(fields) > 6 else ""
                    results.append({
                        "set_number": set_num,
                        "value_type": value_type,
                        "identifier": identifier,
                        "value": value,
                        "unit": unit,
                    })
        return results

    def build_obx(
        self,
        set_number: int,
        value_type: str,
        identifier: str,
        value: str,
        unit: str = "",
        reference_range: str = "",
    ) -> str:
        parts = [
            "OBX",
            str(set_number),
            value_type,
            identifier,
            "",
            value,
            unit,
            reference_range,
        ]
        return "|".join(parts)

    def _split_segments(self, text: str) -> list[str]:
        raw = text.strip().replace("\n", "\r").replace("\r\r", "\r")
        return [s.strip() for s in raw.split("\r") if s.strip()]

    def _determine_type(self, segments: list[str]) -> MessageType:
        for seg in segments:
            if seg.startswith("MSH|"):
                fields = seg.split("|")
                if len(fields) >= 9:
                    msg_type = fields[8] if len(fields) > 8 else ""
                    if msg_type.startswith("ADT"):
                        return MessageType.ADT
                    if msg_type.startswith("ORM"):
                        return MessageType.ORDER
                    if msg_type.startswith("ORU"):
                        return MessageType.OBSERVATION
                    if msg_type.startswith("MDM"):
                        return MessageType.MDM
        return MessageType.OBSERVATION

    def _segments_to_dict(self, segments: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {"_segments": segments}
        for seg in segments:
            fields = seg.split("|")
            if fields[0] == "MSH" and len(fields) > 3:
                result["sending_application"] = fields[2] if len(fields) > 2 else ""
                result["sending_facility"] = fields[3] if len(fields) > 3 else ""
                result["receiving_application"] = fields[4] if len(fields) > 4 else ""
                result["message_type"] = fields[8] if len(fields) > 8 else ""
                result["control_id"] = fields[9] if len(fields) > 9 else ""
            elif fields[0] == "PID" and len(fields) > 3:
                result["patient_id"] = fields[3].split("^")[0] if len(fields) > 3 else ""
                result["patient_name"] = fields[5] if len(fields) > 5 else ""
            elif fields[0] == "OBR" and len(fields) > 2:
                result["order_id"] = fields[2] if len(fields) > 2 else ""
                result["test_code"] = fields[4] if len(fields) > 4 else ""
        return result
