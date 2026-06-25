"""CSV data format handler for LabLink Platform."""
from __future__ import annotations

import csv
import io

from app.protocols.base import MessageDirection, MessageType, ProtocolInterface, ProtocolMessage


class CSVProtocol(ProtocolInterface):
    """CSV data format handler for tabular lab data."""

    @property
    def protocol_name(self) -> str:
        return "CSV"

    def parse(self, raw: bytes | str) -> ProtocolMessage:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        return ProtocolMessage(
            message_type=MessageType.OBSERVATION,
            direction=MessageDirection.INBOUND,
            protocol="CSV",
            payload={"rows": rows, "columns": list(rows[0].keys()) if rows else []},
            raw=raw.encode("utf-8") if isinstance(raw, str) else raw,
        )

    def serialize(self, message: ProtocolMessage) -> bytes:
        rows = message.payload.get("rows", [])
        if not rows:
            return b""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8")

    def validate(self, raw: bytes | str) -> bool:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        try:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            return len(rows) >= 1
        except Exception:
            return False

    def rows_to_observations(self, message: ProtocolMessage) -> list[dict]:
        return message.payload.get("rows", [])
