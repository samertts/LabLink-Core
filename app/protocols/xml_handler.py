"""XML data format handler for LabLink Platform."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from app.protocols.base import MessageDirection, MessageType, ProtocolInterface, ProtocolMessage


class XMLProtocol(ProtocolInterface):
    """XML data format handler for structured lab data."""

    @property
    def protocol_name(self) -> str:
        return "XML"

    def parse(self, raw: bytes | str) -> ProtocolMessage:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        root = ET.fromstring(text)
        data = self._element_to_dict(root)
        msg_type = self._infer_type(root.tag)
        return ProtocolMessage(
            message_type=msg_type,
            direction=MessageDirection.INBOUND,
            protocol="XML",
            payload=data,
            raw=raw.encode("utf-8") if isinstance(raw, str) else raw,
        )

    def serialize(self, message: ProtocolMessage) -> bytes:
        root = self._dict_to_element("root", message.payload)
        return ET.tostring(root, encoding="unicode").encode("utf-8")

    def validate(self, raw: bytes | str) -> bool:
        try:
            text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            ET.fromstring(text)
            return True
        except ET.ParseError:
            return False

    def _element_to_dict(self, element: ET.Element) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if element.attrib:
            result["@attributes"] = dict(element.attrib)
        children = list(element)
        if not children:
            result["text"] = element.text or ""
        else:
            for child in children:
                child_data = self._element_to_dict(child)
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = child_data
        return result

    def _dict_to_element(self, tag: str, data: dict) -> ET.Element:
        element = ET.Element(tag)
        for key, value in data.items():
            if key == "@attributes":
                element.attrib = value
            elif key == "text":
                element.text = str(value)
            elif isinstance(value, list):
                for item in value:
                    child = self._dict_to_element(key, item if isinstance(item, dict) else {"text": str(item)})
                    element.append(child)
            elif isinstance(value, dict):
                child = self._dict_to_element(key, value)
                element.append(child)
            else:
                child = ET.Element(key)
                child.text = str(value)
                element.append(child)
        return element

    def _infer_type(self, tag: str) -> MessageType:
        tag_lower = tag.lower()
        if "observation" in tag_lower or "result" in tag_lower:
            return MessageType.OBSERVATION
        if "patient" in tag_lower:
            return MessageType.PATIENT
        if "order" in tag_lower:
            return MessageType.ORDER
        return MessageType.OBSERVATION
