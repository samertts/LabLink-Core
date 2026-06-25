"""Protocol registry: stores and queries protocol implementations."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.protocols.base import ProtocolInterface, ProtocolMessage

logger = logging.getLogger(__name__)


class ProtocolRegistry:
    """Registry of available protocol implementations.

    Provides lookup by protocol name, message type routing,
    and auto-detection of protocol from raw data.
    """

    def __init__(self) -> None:
        self._protocols: dict[str, ProtocolInterface] = {}
        self._lock = threading.Lock()

    def register(self, protocol: ProtocolInterface) -> None:
        with self._lock:
            self._protocols[protocol.protocol_name.upper()] = protocol
        logger.info("Registered protocol: %s v%s", protocol.protocol_name, protocol.protocol_version)

    def unregister(self, name: str) -> ProtocolInterface | None:
        with self._lock:
            return self._protocols.pop(name.upper(), None)

    def get(self, name: str) -> ProtocolInterface | None:
        return self._protocols.get(name.upper())

    def has(self, name: str) -> bool:
        return name.upper() in self._protocols

    def list_all(self) -> list[str]:
        return list(self._protocols.keys())

    def count(self) -> int:
        return len(self._protocols)

    def detect_protocol(self, raw: bytes | str) -> ProtocolInterface | None:
        """Auto-detect which protocol can handle the given raw data."""
        for protocol in self._protocols.values():
            try:
                if protocol.validate(raw):
                    return protocol
            except Exception:
                continue
        return None

    def parse(self, raw: bytes | str, protocol_name: str | None = None) -> ProtocolMessage | None:
        """Parse raw data using the specified or auto-detected protocol."""
        if protocol_name:
            protocol = self.get(protocol_name)
            if protocol is None:
                raise ValueError(f"Unknown protocol: {protocol_name}")
        else:
            protocol = self.detect_protocol(raw)
            if protocol is None:
                raise ValueError("Could not detect protocol from data")

        return protocol.parse(raw)

    def serialize(self, message: ProtocolMessage, protocol_name: str | None = None) -> bytes:
        """Serialize a message using the specified or message's protocol."""
        name = protocol_name or message.protocol
        protocol = self.get(name)
        if protocol is None:
            raise ValueError(f"Unknown protocol: {name}")
        return protocol.serialize(message)

    def summary(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": proto.protocol_name,
                    "version": proto.protocol_version,
                }
                for proto in self._protocols.values()
            ]
