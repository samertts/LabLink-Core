"""Unit tests for the Communication Protocols (Phase 4)."""

from __future__ import annotations

import json

import pytest

from app.protocols.base import MessageDirection, MessageType, ProtocolMessage
from app.protocols.csv_handler import CSVProtocol
from app.protocols.fhir import FHIRProtocol
from app.protocols.hl7 import HL7Protocol
from app.protocols.registry import ProtocolRegistry
from app.protocols.rest import RESTProtocol
from app.protocols.xml_handler import XMLProtocol

# ── ProtocolMessage Tests ──────────────────────────────────────────


class TestProtocolMessage:
    def test_creation(self) -> None:
        msg = ProtocolMessage(protocol="HL7")
        assert msg.protocol == "HL7"
        assert msg.message_type == MessageType.OBSERVATION
        assert msg.direction == MessageDirection.INBOUND
        assert msg.message_id  # auto-generated

    def test_age(self) -> None:
        msg = ProtocolMessage(timestamp=0.0)
        assert msg.age_seconds > 0

    def test_raw(self) -> None:
        msg = ProtocolMessage(raw=b"test")
        assert msg.raw == b"test"


# ── HL7 Protocol Tests ─────────────────────────────────────────────


class TestHL7Protocol:
    def test_protocol_name(self) -> None:
        proto = HL7Protocol()
        assert proto.protocol_name == "HL7"
        assert proto.protocol_version == "2.5.1"

    def test_parse_valid(self) -> None:
        hl7_msg = (
            "MSH|^~\\&|LabSystem|Hospital|LIS|Lab|20240101||ORU^R01|MSG001|P|2.5.1\r"
            "PID|1||12345^^^Hospital||Doe^John||19800101|M\r"
            "OBR|1||ORD001|CBC^Complete Blood Count\r"
            "OBX|1|NM|WBC^White Blood Cells||7.5|10*3/uL|4.5-11.0\r"
        )
        proto = HL7Protocol()
        msg = proto.parse(hl7_msg)
        assert msg.protocol == "HL7"
        assert msg.message_type == MessageType.OBSERVATION
        assert msg.payload.get("patient_id") == "12345"
        assert msg.payload.get("sending_application") == "LabSystem"

    def test_parse_bytes(self) -> None:
        hl7_msg = b"MSH|^~\\&|Lab|Hosp|LIS|Lab|20240101||ORU^R01|MSG001|P|2.5.1\r"
        proto = HL7Protocol()
        msg = proto.parse(hl7_msg)
        assert msg.protocol == "HL7"

    def test_validate(self) -> None:
        proto = HL7Protocol()
        assert proto.validate("MSH|^~\\&|Lab|Hosp|LIS|Lab|20240101||ORU^R01|MSG001|P|2.5.1") is True
        assert proto.validate("not hl7") is False
        assert proto.validate("") is False

    def test_serialize(self) -> None:
        proto = HL7Protocol()
        msg = ProtocolMessage(
            message_type=MessageType.ACKNOWLEDGMENT,
            protocol="HL7",
            payload={"accepted": True, "control_id": "MSG001"},
        )
        raw = proto.serialize(msg)
        assert b"MSA|AA|MSG001" in raw

    def test_get_message_type(self) -> None:
        proto = HL7Protocol()
        adt = "MSH|^~\\&|Lab|Hosp|||20240101||ADT^A01|MSG001|P|2.5.1"
        assert proto.get_message_type(adt) == MessageType.ADT

        oru = "MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1"
        assert proto.get_message_type(oru) == MessageType.OBSERVATION

    def test_parse_obx_segments(self) -> None:
        hl7_msg = (
            "MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1\r"
            "OBX|1|NM|WBC^White Blood Cells||7.5|10*3/uL|4.5-11.0\r"
            "OBX|2|NM|HGB^Hemoglobin||14.2|g/dL|12.0-16.0\r"
        )
        proto = HL7Protocol()
        msg = proto.parse(hl7_msg)
        obx_list = proto.parse_obx_segments(msg)
        assert len(obx_list) == 2
        assert obx_list[0]["identifier"] == "WBC^White Blood Cells"
        assert obx_list[1]["value"] == "14.2"

    def test_build_obx(self) -> None:
        proto = HL7Protocol()
        obx = proto.build_obx(1, "NM", "WBC", "7.5", "10*3/uL", "4.5-11.0")
        assert obx.startswith("OBX|1|NM|WBC|")
        assert "7.5" in obx
        assert "10*3/uL" in obx

    def test_create_ack(self) -> None:
        proto = HL7Protocol()
        original = ProtocolMessage(message_id="msg-123", protocol="HL7", source="Lab", destination="LIS")
        ack = proto.create_ack(original, accepted=True)
        assert ack.message_type == MessageType.ACKNOWLEDGMENT
        assert ack.direction == MessageDirection.OUTBOUND
        assert ack.payload["control_id"] == "msg-123"
        assert ack.payload["accepted"] is True


# ── FHIR Protocol Tests ────────────────────────────────────────────


class TestFHIRProtocol:
    def test_protocol_name(self) -> None:
        proto = FHIRProtocol()
        assert proto.protocol_name == "FHIR"
        assert proto.protocol_version == "R4"

    def test_parse_observation(self) -> None:
        obs = {
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "2345-7"}]},
            "valueQuantity": {"value": 5.4, "unit": "mmol/L"},
        }
        proto = FHIRProtocol()
        msg = proto.parse(json.dumps(obs))
        assert msg.message_type == MessageType.OBSERVATION
        assert msg.payload["resourceType"] == "Observation"

    def test_parse_patient(self) -> None:
        patient = {"resourceType": "Patient", "id": "p1", "name": [{"family": "Doe"}]}
        proto = FHIRProtocol()
        msg = proto.parse(json.dumps(patient))
        assert msg.message_type == MessageType.PATIENT

    def test_validate(self) -> None:
        proto = FHIRProtocol()
        assert proto.validate(json.dumps({"resourceType": "Observation"})) is True
        assert proto.validate("not json") is False
        assert proto.validate("{}") is False

    def test_serialize(self) -> None:
        proto = FHIRProtocol()
        msg = ProtocolMessage(protocol="FHIR", payload={"resourceType": "Observation"})
        raw = proto.serialize(msg)
        data = json.loads(raw)
        assert data["resourceType"] == "Observation"

    def test_create_observation(self) -> None:
        proto = FHIRProtocol()
        obs = proto.create_observation(code="2345-7", value=5.4, unit="mmol/L", patient_id="p1")
        assert obs["resourceType"] == "Observation"
        assert obs["valueQuantity"]["value"] == 5.4

    def test_create_patient(self) -> None:
        proto = FHIRProtocol()
        patient = proto.create_patient("p1", "Doe", "John")
        assert patient["resourceType"] == "Patient"
        assert patient["name"][0]["family"] == "Doe"

    def test_create_diagnostic_report(self) -> None:
        proto = FHIRProtocol()
        report = proto.create_diagnostic_report("p1", [{"id": "obs1"}])
        assert report["resourceType"] == "DiagnosticReport"

    def test_extract_observations(self) -> None:
        proto = FHIRProtocol()
        bundle = {
            "resourceType": "Bundle",
            "entry": [
                {"resource": {"resourceType": "Observation", "code": {"coding": [{"code": "2345-7"}]}}},
                {"resource": {"resourceType": "Patient"}},
            ],
        }
        msg = ProtocolMessage(protocol="FHIR", payload=bundle)
        obs = proto.extract_observations(msg)
        assert len(obs) == 1

    def test_extract_single_observation(self) -> None:
        proto = FHIRProtocol()
        obs = {"resourceType": "Observation", "code": {"coding": []}}
        msg = ProtocolMessage(protocol="FHIR", payload=obs)
        result = proto.extract_observations(msg)
        assert len(result) == 1


# ── REST Protocol Tests ────────────────────────────────────────────


class TestRESTProtocol:
    def test_parse(self) -> None:
        proto = RESTProtocol()
        data = {"patient_id": "p1", "results": [{"test": "WBC", "value": 7.5}]}
        msg = proto.parse(json.dumps(data))
        assert msg.protocol == "REST"
        assert msg.message_type == MessageType.OBSERVATION

    def test_validate(self) -> None:
        proto = RESTProtocol()
        assert proto.validate('{"key": "value"}') is True
        assert proto.validate("not json") is False

    def test_serialize(self) -> None:
        proto = RESTProtocol()
        msg = ProtocolMessage(protocol="REST", payload={"key": "value"})
        raw = proto.serialize(msg)
        assert b"key" in raw

    def test_create_result_payload(self) -> None:
        proto = RESTProtocol()
        payload = proto.create_result_payload("p1", [{"test": "WBC", "value": 7.5}])
        assert payload["patient_id"] == "p1"
        assert len(payload["results"]) == 1


# ── CSV Protocol Tests ─────────────────────────────────────────────


class TestCSVProtocol:
    def test_parse(self) -> None:
        csv_data = "patient_id,test_code,value,unit\np1,WBC,7.5,10*3/uL\np1,HGB,14.2,g/dL\n"
        proto = CSVProtocol()
        msg = proto.parse(csv_data)
        assert msg.protocol == "CSV"
        rows = msg.payload["rows"]
        assert len(rows) == 2
        assert rows[0]["test_code"] == "WBC"

    def test_validate(self) -> None:
        proto = CSVProtocol()
        assert proto.validate("col1,col2\nval1,val2\n") is True
        assert proto.validate("") is False

    def test_serialize(self) -> None:
        proto = CSVProtocol()
        msg = ProtocolMessage(protocol="CSV", payload={"rows": [{"a": "1", "b": "2"}]})
        raw = proto.parse(proto.serialize(msg).decode("utf-8"))
        assert raw.payload["rows"][0]["a"] == "1"

    def test_rows_to_observations(self) -> None:
        proto = CSVProtocol()
        csv_data = "test,value\nWBC,7.5\n"
        msg = proto.parse(csv_data)
        obs = proto.rows_to_observations(msg)
        assert len(obs) == 1
        assert obs[0]["test"] == "WBC"


# ── XML Protocol Tests ─────────────────────────────────────────────


class TestXMLProtocol:
    def test_parse(self) -> None:
        xml_data = "<LabResult><Patient><ID>p1</ID><Name>Doe</Name></Patient><Test name=\"WBC\">7.5</Test></LabResult>"
        proto = XMLProtocol()
        msg = proto.parse(xml_data)
        assert msg.protocol == "XML"

    def test_validate(self) -> None:
        proto = XMLProtocol()
        assert proto.validate("<root/>") is True
        assert proto.validate("not xml") is False

    def test_serialize(self) -> None:
        proto = XMLProtocol()
        msg = ProtocolMessage(protocol="XML", payload={"root": {"child": {"text": "value"}}})
        raw = proto.serialize(msg)
        assert b"child" in raw

    def test_roundtrip(self) -> None:
        proto = XMLProtocol()
        xml_data = "<Result><Test>WBC</Test><Value>7.5</Value></Result>"
        msg = proto.parse(xml_data)
        serialized = proto.serialize(msg)
        msg2 = proto.parse(serialized.decode("utf-8"))
        assert msg2.payload.get("Test", {}).get("text") == "WBC"
        assert msg2.payload.get("Value", {}).get("text") == "7.5"


# ── ProtocolRegistry Tests ─────────────────────────────────────────


class TestProtocolRegistry:
    def test_register_unregister(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        assert reg.has("HL7")
        assert reg.count() == 1

        reg.unregister("HL7")
        assert reg.has("HL7") is False

    def test_get(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        proto = reg.get("hl7")
        assert isinstance(proto, HL7Protocol)

    def test_detect_protocol(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        reg.register(FHIRProtocol())
        reg.register(CSVProtocol())

        hl7_data = "MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1"
        detected = reg.detect_protocol(hl7_data)
        assert detected is not None
        assert detected.protocol_name == "HL7"

        fhir_data = json.dumps({"resourceType": "Observation"})
        detected = reg.detect_protocol(fhir_data)
        assert detected is not None
        assert detected.protocol_name == "FHIR"

    def test_parse_with_detection(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        reg.register(FHIRProtocol())

        hl7_data = "MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1"
        msg = reg.parse(hl7_data)
        assert msg is not None
        assert msg.protocol == "HL7"

    def test_parse_explicit_protocol(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        hl7_data = "MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1"
        msg = reg.parse(hl7_data, protocol_name="HL7")
        assert msg is not None

    def test_parse_unknown_protocol(self) -> None:
        reg = ProtocolRegistry()
        with pytest.raises(ValueError, match="Unknown protocol"):
            reg.parse("data", protocol_name="UNKNOWN")

    def test_parse_no_detection(self) -> None:
        reg = ProtocolRegistry()
        with pytest.raises(ValueError, match="Could not detect"):
            reg.parse("random data that matches nothing")

    def test_serialize(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        msg = ProtocolMessage(
            message_type=MessageType.ACKNOWLEDGMENT,
            protocol="HL7",
            payload={"accepted": True, "control_id": "MSG001"},
        )
        raw = reg.serialize(msg)
        assert b"MSA|AA" in raw

    def test_serialize_explicit_protocol(self) -> None:
        reg = ProtocolRegistry()
        reg.register(FHIRProtocol())
        msg = ProtocolMessage(protocol="FHIR", payload={"resourceType": "Observation"})
        raw = reg.serialize(msg, protocol_name="FHIR")
        data = json.loads(raw)
        assert data["resourceType"] == "Observation"

    def test_summary(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        reg.register(FHIRProtocol())
        s = reg.summary()
        assert len(s) == 2
        names = {p["name"] for p in s}
        assert "HL7" in names
        assert "FHIR" in names

    def test_list_all(self) -> None:
        reg = ProtocolRegistry()
        reg.register(HL7Protocol())
        reg.register(RESTProtocol())
        assert sorted(reg.list_all()) == ["HL7", "REST"]
