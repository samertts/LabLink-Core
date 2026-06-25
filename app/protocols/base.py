"""Protocol interface ABC, message types, and configuration."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageType(Enum):
    """Standard message types across protocols."""

    OBSERVATION = "observation"
    ORDER = "order"
    QUERY = "query"
    ACKNOWLEDGMENT = "acknowledgment"
    PATIENT = "patient"
    ADT = "adt"  # Admission, Discharge, Transfer
    ORU = "oru"  # Observation Result
    OML = "oml"  # Order Message
    MDM = "mdm"  # Medical Document Management


class MessageDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


@dataclass(slots=True)
class ProtocolMessage:
    """Universal message envelope for all protocols."""

    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.OBSERVATION
    direction: MessageDirection = MessageDirection.INBOUND
    protocol: str = ""
    timestamp: float = field(default_factory=time.time)
    source: str = ""
    destination: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    raw: bytes = b""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.timestamp


@dataclass(slots=True)
class ProtocolConfig:
    """Configuration for a protocol handler."""

    timeout_seconds: float = 30.0
    max_message_size: int = 1_048_576  # 1MB
    encoding: str = "utf-8"
    custom: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.custom.get(key, default)


class ProtocolInterface(ABC):
    """Abstract base class for all protocol implementations.

    Each protocol (HL7, FHIR, ASTM, REST, CSV, XML, JSON) implements
    this interface to provide a uniform API for message handling.
    """

    @property
    @abstractmethod
    def protocol_name(self) -> str:
        """Canonical protocol name (e.g. ``"HL7"``, ``"FHIR"``)."""

    @property
    def protocol_version(self) -> str:
        return "1.0"

    @abstractmethod
    def parse(self, raw: bytes | str) -> ProtocolMessage:
        """Parse raw bytes/string into a ProtocolMessage."""

    @abstractmethod
    def serialize(self, message: ProtocolMessage) -> bytes:
        """Serialize a ProtocolMessage to raw bytes."""

    @abstractmethod
    def validate(self, raw: bytes | str) -> bool:
        """Validate that raw data conforms to this protocol."""

    def get_message_type(self, raw: bytes | str) -> MessageType | None:
        """Extract the message type from raw data without full parsing."""
        return None

    def get_sequence_number(self, raw: bytes | str) -> str | None:
        """Extract a sequence/control number from raw data."""
        return None

    def create_ack(self, message: ProtocolMessage, accepted: bool = True) -> ProtocolMessage:
        """Create an acknowledgment for a received message."""
        return ProtocolMessage(
            message_type=MessageType.ACKNOWLEDGMENT,
            direction=MessageDirection.OUTBOUND,
            protocol=self.protocol_name,
            source=message.destination,
            destination=message.source,
            payload={"control_id": message.message_id, "accepted": accepted},
            metadata={"ack_for": message.message_id},
        )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} protocol={self.protocol_name} v{self.protocol_version}>"
