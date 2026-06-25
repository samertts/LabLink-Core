"""Unit tests for the Device Discovery engine (Phase 5)."""

from __future__ import annotations

from app.discovery.base import DiscoveredDevice, DiscoveryConfig
from app.discovery.engine import DeviceDiscoveryEngine
from app.discovery.fingerprint import DeviceFingerprint, FingerprintResult
from app.discovery.recommender import DriverRecommender
from app.vendors.builtins import MindrayVendorPackage, SysmexVendorPackage
from app.vendors.registry import VendorRegistry

# ── DiscoveryConfig Tests ──────────────────────────────────────────


class TestDiscoveryConfig:
    def test_defaults(self) -> None:
        cfg = DiscoveryConfig()
        assert cfg.scan_timeout_seconds == 2.0
        assert 23 in cfg.tcp_ports
        assert cfg.max_concurrent == 50


# ── DiscoveredDevice Tests ─────────────────────────────────────────


class TestDiscoveredDevice:
    def test_creation(self) -> None:
        d = DiscoveredDevice(device_id="d1", address="192.168.1.10", port=4000)
        assert d.device_id == "d1"
        assert d.is_online is True

    def test_to_dict(self) -> None:
        d = DiscoveredDevice(device_id="d1", address="192.168.1.10")
        result = d.to_dict()
        assert result["device_id"] == "d1"
        assert result["address"] == "192.168.1.10"


# ── DeviceFingerprint Tests ────────────────────────────────────────


class TestDeviceFingerprint:
    def test_identify_sysmex(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Sysmex XN-1000 hematology analyzer ready")
        assert result.vendor == "Sysmex"
        assert result.model == "XN"
        assert result.protocol == "ASTM"
        assert result.confidence > 0

    def test_identify_mindray(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Mindray BC-2800 auto hematology analyzer")
        assert result.vendor == "Mindray"
        assert result.model == "BC"

    def test_identify_roche(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Roche cobas 8800 molecular system")
        assert result.vendor == "Roche"
        assert result.model == "cobas"

    def test_identify_abbott(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Abbott Alinity s immunoassay")
        assert result.vendor == "Abbott"
        assert result.model == "Alinity"

    def test_identify_siemens(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Siemens Atellica CH clinical chemistry")
        assert result.vendor == "Siemens"
        assert result.model == "Atellica"

    def test_identify_beckman(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Beckman Coulter DxH 800 hematology")
        assert result.vendor == "Beckman Coulter"
        assert result.model == "DxH"

    def test_identify_biorad(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("Bio-Rad IH-1000 immunohematology")
        assert result.vendor == "Bio-Rad"
        assert result.model == "IH-1000"

    def test_identify_unknown(self) -> None:
        fp = DeviceFingerprint()
        result = fp.identify("generic device data")
        assert result.vendor == "unknown"
        assert result.confidence == 0.0

    def test_detect_protocol_hl7(self) -> None:
        fp = DeviceFingerprint()
        proto = fp.detect_protocol("MSH|^~\\&|Lab|Hosp|||20240101||ORU^R01|MSG001|P|2.5.1")
        assert proto == "HL7"

    def test_detect_protocol_astm(self) -> None:
        fp = DeviceFingerprint()
        proto = fp.detect_protocol("20240101120000\rOBR|1|test\r")
        assert proto == "ASTM"

    def test_detect_protocol_fhir(self) -> None:
        fp = DeviceFingerprint()
        import json
        proto = fp.detect_protocol(json.dumps({"resourceType": "Observation"}))
        assert proto == "FHIR"

    def test_detect_protocol_unknown(self) -> None:
        fp = DeviceFingerprint()
        proto = fp.detect_protocol("random garbage data")
        assert proto == "unknown"

    def test_register_pattern(self) -> None:
        fp = DeviceFingerprint()
        fp.register_pattern("CustomVendor", "ModelX", ["CustomVendor", "ModelX"], "HL7")
        result = fp.identify("CustomVendor ModelX connected")
        assert result.vendor == "CustomVendor"
        assert result.model == "ModelX"


# ── DriverRecommender Tests ────────────────────────────────────────


class TestDriverRecommender:
    def test_recommend_with_registry(self) -> None:
        reg = VendorRegistry()
        reg.register(SysmexVendorPackage())
        rec = DriverRecommender(reg)

        fp = FingerprintResult(vendor="Sysmex", model="XN-1000", protocol="ASTM", confidence=0.9)
        result = rec.recommend(fp)
        assert result is not None
        assert result.vendor == "Sysmex"
        assert result.model == "XN-1000"

    def test_recommend_without_registry(self) -> None:
        rec = DriverRecommender()
        fp = FingerprintResult(vendor="Sysmex", model="XN-1000", protocol="ASTM", confidence=0.9)
        result = rec.recommend(fp)
        assert result is not None
        assert result.vendor == "Sysmex"
        assert result.confidence < 1.0  # reduced without registry

    def test_recommend_unknown(self) -> None:
        rec = DriverRecommender()
        fp = FingerprintResult(vendor="unknown", model="unknown", protocol="unknown")
        result = rec.recommend(fp)
        assert result is None

    def test_recommend_all(self) -> None:
        reg = VendorRegistry()
        reg.register(SysmexVendorPackage())
        reg.register(MindrayVendorPackage())
        rec = DriverRecommender(reg)

        fp = FingerprintResult(vendor="Sysmex", model="XN-1000", protocol="ASTM", confidence=0.9)
        results = rec.recommend_all(fp)
        assert len(results) >= 1  # at least the primary recommendation


# ── DeviceDiscoveryEngine Tests ────────────────────────────────────


class TestDeviceDiscoveryEngine:
    def test_creation(self) -> None:
        engine = DeviceDiscoveryEngine()
        assert engine.discovered == []

    def test_creation_with_config(self) -> None:
        cfg = DiscoveryConfig(scan_timeout_seconds=1.0)
        engine = DeviceDiscoveryEngine(config=cfg)
        assert engine._config.scan_timeout_seconds == 1.0

    def test_creation_with_registry(self) -> None:
        reg = VendorRegistry()
        reg.register(SysmexVendorPackage())
        engine = DeviceDiscoveryEngine(vendor_registry=reg)
        assert engine._recommender._vendor_registry is reg

    def test_scan_tcp_refused(self) -> None:
        engine = DeviceDiscoveryEngine()
        result = engine.scan_tcp("127.0.0.1", 19999, timeout=0.1)
        assert result is None

    def test_recommend_driver(self) -> None:
        engine = DeviceDiscoveryEngine()
        device = DiscoveredDevice(
            device_id="d1",
            address="192.168.1.10",
            vendor="Sysmex",
            model="XN-1000",
            protocol="ASTM",
        )
        rec = engine.recommend_driver(device)
        assert rec is not None
        assert rec.vendor == "Sysmex"

    def test_summary_empty(self) -> None:
        engine = DeviceDiscoveryEngine()
        s = engine.summary()
        assert s["total"] == 0

    def test_discover_all_empty_config(self) -> None:
        cfg = DiscoveryConfig(tcp_host_range="127.0.0.1", tcp_ports=(1,), serial_ports=())
        engine = DeviceDiscoveryEngine(config=cfg)
        results = engine.discover_all(cfg)
        assert isinstance(results, list)

    def test_scan_serial_not_available(self) -> None:
        engine = DeviceDiscoveryEngine()
        results = engine.scan_serial("/dev/nonexistent")
        assert results == []
