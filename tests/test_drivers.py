"""Unit tests for the Driver SDK (Phase 2)."""

from __future__ import annotations

from typing import Any

import pytest

from app.drivers.base import BaseDriver, ConnectionState, DeviceCapabilities, DeviceMetadata, DriverConfig
from app.drivers.diagnostics import DiagnosticReport, DriverDiagnostics
from app.drivers.errors import (
    AuthenticationError,
    ConnectionError,
    DataError,
    DriverError,
    DriverWarning,
    ProtocolError,
    RecoveryAction,
    TimeoutError,
)
from app.drivers.health import DeviceHealth, HealthCheckResult
from app.drivers.manager import DriverManager
from app.drivers.recovery import RecoveryStrategy

# ── Test Drivers ───────────────────────────────────────────────────


class MockDriver(BaseDriver):
    """A mock driver for testing."""

    def __init__(self, device_id: str = "mock-001", **kwargs) -> None:
        metadata = DeviceMetadata(
            device_id=device_id,
            vendor="TestVendor",
            model="TestModel",
            protocol="ASTM",
            transport="tcp",
        )
        super().__init__(metadata=metadata, **kwargs)
        self._connected = False
        self._sent: list[bytes] = []
        self._read_buffer = b"OK\r\n"

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def read_data(self) -> bytes:
        return self._read_buffer

    def write_data(self, data: bytes) -> None:
        self._sent.append(data)

    def set_read_data(self, data: bytes) -> None:
        self._read_buffer = data

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            supports_realtime=True,
            supports_batch=True,
            supported_protocols=("ASTM", "HL7"),
            supported_parameters=("HGB", "WBC", "PLT"),
        )


class FailingDriver(BaseDriver):
    """A driver that fails on connect/read/write."""

    def __init__(self) -> None:
        metadata = DeviceMetadata(device_id="fail-001", vendor="Fail", model="F1")
        super().__init__(metadata=metadata)

    def connect(self) -> None:
        raise ConnectionError("Cannot reach device", device_id=self.device_id)

    def disconnect(self) -> None:
        pass

    def read_data(self) -> bytes:
        raise TimeoutError("Read timed out", device_id=self.device_id)

    def write_data(self, data: bytes) -> None:
        raise DriverError("Write failed", device_id=self.device_id)


class SlowDriver(MockDriver):
    """A driver that simulates slow health checks."""

    def health_check(self) -> dict[str, Any]:
        return {"status": "degraded", "message": "High latency"}


# ── DeviceMetadata Tests ───────────────────────────────────────────


class TestDeviceMetadata:
    def test_creation(self) -> None:
        m = DeviceMetadata(device_id="d1", vendor="V", model="M")
        assert m.device_id == "d1"
        assert m.vendor == "V"
        assert m.model == "M"
        assert m.protocol == "ASTM"

    def test_display_name(self) -> None:
        m = DeviceMetadata(device_id="d1", vendor="Sysmex", model="XN-1000")
        assert "Sysmex" in m.display_name
        assert "XN-1000" in m.display_name
        assert "d1" in m.display_name

    def test_frozen(self) -> None:
        m = DeviceMetadata(device_id="d1", vendor="V", model="M")
        with pytest.raises(AttributeError):
            m.device_id = "d2"  # type: ignore[misc]

    def test_defaults(self) -> None:
        m = DeviceMetadata(device_id="d1", vendor="V", model="M")
        assert m.serial_number == ""
        assert m.firmware_version == ""
        assert m.device_class == "unknown"
        assert m.transport == "tcp"


# ── DeviceCapabilities Tests ───────────────────────────────────────


class TestDeviceCapabilities:
    def test_defaults(self) -> None:
        caps = DeviceCapabilities()
        assert caps.supports_realtime is True
        assert caps.supports_batch is False
        assert caps.max_concurrent_sessions == 1
        assert "ASTM" in caps.supported_protocols

    def test_custom(self) -> None:
        caps = DeviceCapabilities(
            supports_realtime=False,
            supports_batch=True,
            max_concurrent_sessions=4,
        )
        assert caps.supports_realtime is False
        assert caps.supports_batch is True
        assert caps.max_concurrent_sessions == 4


# ── DriverConfig Tests ─────────────────────────────────────────────


class TestDriverConfig:
    def test_defaults(self) -> None:
        cfg = DriverConfig()
        assert cfg.connection_timeout_seconds == 10.0
        assert cfg.retry_count == 3
        assert cfg.custom == {}

    def test_custom_config(self) -> None:
        cfg = DriverConfig(custom={"baudrate": 9600, "parity": "N"})
        assert cfg.get("baudrate") == 9600
        assert cfg.get("parity") == "N"
        assert cfg.get("missing", "default") == "default"


# ── BaseDriver Tests ───────────────────────────────────────────────


class TestBaseDriver:
    def test_lifecycle(self) -> None:
        driver = MockDriver()
        assert driver.state == ConnectionState.DISCONNECTED
        assert driver.is_connected is False

        driver._set_state(ConnectionState.CONNECTED)
        driver.connect()
        assert driver.is_connected is True

        driver.disconnect()
        driver._set_state(ConnectionState.DISCONNECTED)
        assert driver.is_connected is False

    def test_send_command(self) -> None:
        driver = MockDriver()
        driver.set_read_data(b"RESULT:OK\r\n")
        result = driver.send_command("STATUS")
        assert result == "RESULT:OK\r\n"
        assert driver._sent == [b"STATUS"]

    def test_capabilities(self) -> None:
        driver = MockDriver()
        caps = driver.capabilities()
        assert caps.supports_realtime is True
        assert caps.supports_batch is True
        assert "HL7" in caps.supported_protocols

    def test_health_check(self) -> None:
        driver = MockDriver()
        health = driver.health_check()
        assert health["status"] == "degraded"  # not connected

    def test_collect_diagnostics(self) -> None:
        driver = MockDriver()
        diag = driver.collect_diagnostics()
        assert diag["device_id"] == "mock-001"
        assert diag["vendor"] == "TestVendor"
        assert diag["state"] == "disconnected"

    def test_error_recording(self) -> None:
        driver = MockDriver()
        driver._record_error("test error")
        assert driver.error_count == 1
        assert driver.last_error == "test error"
        assert driver.state == ConnectionState.ERROR

    def test_clear_error(self) -> None:
        driver = MockDriver()
        driver._record_error("test error")
        driver._clear_error()
        assert driver.last_error is None

    def test_repr(self) -> None:
        driver = MockDriver()
        r = repr(driver)
        assert "MockDriver" in r
        assert "mock-001" in r

    def test_metadata_properties(self) -> None:
        driver = MockDriver()
        assert driver.device_id == "mock-001"
        assert driver.metadata.vendor == "TestVendor"


# ── Driver Error Tests ─────────────────────────────────────────────


class TestDriverErrors:
    def test_driver_error(self) -> None:
        err = DriverError("something broke", code="ERR_1", device_id="d1")
        assert str(err) == "something broke"
        assert err.code == "ERR_1"
        assert err.device_id == "d1"
        assert err.recoverable is True
        assert err.recovery_action == RecoveryAction.RETRY

    def test_to_dict(self) -> None:
        err = DriverError("fail", code="X", device_id="d1")
        d = err.to_dict()
        assert d["code"] == "X"
        assert d["device_id"] == "d1"
        assert d["recoverable"] is True

    def test_connection_error(self) -> None:
        err = ConnectionError("timeout")
        assert err.code == "CONNECTION_ERROR"
        assert err.recovery_action == RecoveryAction.RECONNECT

    def test_timeout_error(self) -> None:
        err = TimeoutError("read timeout")
        assert err.code == "TIMEOUT"

    def test_protocol_error(self) -> None:
        err = ProtocolError("bad frame")
        assert err.code == "PROTOCOL_ERROR"
        assert err.recoverable is False

    def test_auth_error(self) -> None:
        err = AuthenticationError("unauthorized")
        assert err.code == "AUTH_ERROR"
        assert err.recovery_action == RecoveryAction.ESCALATE

    def test_data_error(self) -> None:
        err = DataError("checksum mismatch")
        assert err.code == "DATA_ERROR"

    def test_driver_warning(self) -> None:
        w = DriverWarning(code="W1", message="low battery")
        assert w.code == "W1"
        assert w.recovery_action == RecoveryAction.NONE


# ── Health Tests ────────────────────────────────────────────────────


class TestDeviceHealth:
    def test_creation(self) -> None:
        h = DeviceHealth(device_id="d1")
        assert h.device_id == "d1"
        assert h.status == "unknown"

    def test_to_dict(self) -> None:
        h = DeviceHealth(device_id="d1", status="healthy", total_checks=10)
        d = h.to_dict()
        assert d["device_id"] == "d1"
        assert d["status"] == "healthy"
        assert d["total_checks"] == 10


class TestHealthCheckResult:
    def test_creation(self) -> None:
        r = HealthCheckResult(device_id="d1", status="healthy")
        assert r.device_id == "d1"
        assert r.status == "healthy"
        assert r.checked_at > 0


# ── Diagnostics Tests ──────────────────────────────────────────────


class TestDriverDiagnostics:
    def test_register_unregister(self) -> None:
        diag = DriverDiagnostics()
        diag.register("d1")
        assert "d1" in diag.get_all_device_ids()
        diag.unregister("d1")
        assert "d1" not in diag.get_all_device_ids()

    def test_record_and_get(self) -> None:
        diag = DriverDiagnostics()
        report = DiagnosticReport(device_id="d1", driver_info={"vendor": "V"})
        diag.record(report)
        latest = diag.get_latest("d1")
        assert latest is not None
        assert latest.driver_info["vendor"] == "V"

    def test_history_limit(self) -> None:
        diag = DriverDiagnostics()
        for _ in range(60):
            diag.record(DiagnosticReport(device_id="d1"))
        history = diag.get_history("d1", limit=100)
        assert len(history) <= 50  # MAX_REPORTS_PER_DEVICE

    def test_summary(self) -> None:
        diag = DriverDiagnostics()
        diag.record(DiagnosticReport(device_id="d1", errors=[{"msg": "fail"}]))
        summary = diag.get_summary()
        assert summary["device_count"] == 1
        assert summary["total_errors"] == 1

    def test_collect_from_driver(self) -> None:
        diag = DriverDiagnostics()
        driver = MockDriver()
        report = diag.collect_from_driver(driver)
        assert report.device_id == "mock-001"

    def test_get_latest_empty(self) -> None:
        diag = DriverDiagnostics()
        assert diag.get_latest("nonexistent") is None


class TestDiagnosticReport:
    def test_to_dict(self) -> None:
        report = DiagnosticReport(
            device_id="d1",
            driver_info={"vendor": "V"},
            errors=[{"msg": "e1"}],
        )
        d = report.to_dict()
        assert d["device_id"] == "d1"
        assert d["summary"]["error_count"] == 1
        assert d["summary"]["healthy"] is False

    def test_empty_report_healthy(self) -> None:
        report = DiagnosticReport(device_id="d1")
        d = report.to_dict()
        assert d["summary"]["healthy"] is True


# ── Recovery Tests ─────────────────────────────────────────────────


class TestRecoveryStrategy:
    def test_initial_state(self) -> None:
        strategy = RecoveryStrategy()
        assert strategy.is_circuit_open is False
        stats = strategy.get_stats()
        assert stats["total_attempts"] == 0

    def test_handle_error_retries(self) -> None:
        strategy = RecoveryStrategy(max_retries=3)
        error = DriverError("fail")
        for _ in range(2):
            action = strategy.handle_error(error)
            assert action == RecoveryAction.RETRY

    def test_handle_error_escalates(self) -> None:
        strategy = RecoveryStrategy(max_retries=2, max_reconnect_attempts=2)
        error = DriverError("fail")
        for _ in range(5):
            strategy.handle_error(error)
        stats = strategy.get_stats()
        assert stats["consecutive_failures"] == 5

    def test_non_recoverable(self) -> None:
        strategy = RecoveryStrategy()
        error = DriverError("bad", recoverable=False)
        action = strategy.handle_error(error)
        assert action == RecoveryAction.ESCALATE

    def test_circuit_breaker(self) -> None:
        strategy = RecoveryStrategy(circuit_breaker_threshold=3)
        error = DriverError("fail")
        for _ in range(3):
            strategy.handle_error(error)
        assert strategy.is_circuit_open is True

    def test_record_success_resets(self) -> None:
        strategy = RecoveryStrategy()
        error = DriverError("fail")
        strategy.handle_error(error)
        strategy.handle_error(error)
        strategy.record_success()
        assert strategy.get_stats()["consecutive_failures"] == 0

    def test_reset(self) -> None:
        strategy = RecoveryStrategy(circuit_breaker_threshold=2)
        error = DriverError("fail")
        strategy.handle_error(error)
        strategy.handle_error(error)
        assert strategy.is_circuit_open is True
        strategy.reset()
        assert strategy.is_circuit_open is False

    def test_history(self) -> None:
        strategy = RecoveryStrategy()
        error = DriverError("fail")
        strategy.handle_error(error)
        history = strategy.get_history()
        assert len(history) == 1

    def test_register_handler(self) -> None:
        strategy = RecoveryStrategy()
        called = []
        strategy.register_handler(RecoveryAction.RETRY, lambda: (called.append(True), True)[-1])
        error = DriverError("fail")
        strategy.handle_error(error)
        assert len(called) == 1


# ── DriverManager Tests ────────────────────────────────────────────


class TestDriverManager:
    def test_register_unregister(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        assert mgr.get("mock-001") is driver
        assert mgr.count() == 1

        mgr.unregister("mock-001")
        assert mgr.get("mock-001") is None
        assert mgr.count() == 0

    def test_connect_disconnect(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        mgr.connect("mock-001")
        assert driver.is_connected is True

        mgr.disconnect("mock-001")
        assert driver.is_connected is False

    def test_connect_nonexistent(self) -> None:
        mgr = DriverManager()
        with pytest.raises(KeyError):
            mgr.connect("no-such")

    def test_connect_all(self) -> None:
        mgr = DriverManager()
        d1 = MockDriver(device_id="d1")
        d2 = MockDriver(device_id="d2")
        mgr.register(d1)
        mgr.register(d2)
        results = mgr.connect_all()
        assert results["d1"] is True
        assert results["d2"] is True

    def test_disconnect_all(self) -> None:
        mgr = DriverManager()
        d1 = MockDriver(device_id="d1")
        d2 = MockDriver(device_id="d2")
        mgr.register(d1)
        mgr.register(d2)
        mgr.connect_all()
        mgr.disconnect_all()
        assert d1.is_connected is False
        assert d2.is_connected is False

    def test_health_check(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        result = mgr.health_check("mock-001")
        assert result.device_id == "mock-001"
        assert result.status in ("healthy", "degraded")

    def test_health_check_nonexistent(self) -> None:
        mgr = DriverManager()
        result = mgr.health_check("no-such")
        assert result.status == "unhealthy"

    def test_health_check_all(self) -> None:
        mgr = DriverManager()
        mgr.register(MockDriver(device_id="d1"))
        mgr.register(MockDriver(device_id="d2"))
        results = mgr.health_check_all()
        assert len(results) == 2

    def test_get_device_health(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        mgr.health_check("mock-001")
        health = mgr.get_device_health("mock-001")
        assert health.device_id == "mock-001"
        assert health.total_checks == 1

    def test_diagnostics(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        report = mgr.collect_diagnostics("mock-001")
        assert report is not None
        assert report.device_id == "mock-001"

    def test_diagnostics_all(self) -> None:
        mgr = DriverManager()
        mgr.register(MockDriver(device_id="d1"))
        mgr.register(MockDriver(device_id="d2"))
        reports = mgr.collect_all_diagnostics()
        assert len(reports) == 2

    def test_read_write_data(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        driver.set_read_data(b"DATA")
        data = mgr.read_data("mock-001")
        assert data == b"DATA"

        mgr.write_data("mock-001", b"CMD")
        assert driver._sent == [b"CMD"]

    def test_send_command(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        driver.set_read_data(b"RESULT")
        mgr.register(driver)
        result = mgr.send_command("mock-001", "STATUS")
        assert result == "RESULT"

    def test_summary(self) -> None:
        mgr = DriverManager()
        mgr.register(MockDriver(device_id="d1"))
        summary = mgr.summary()
        assert len(summary) == 1
        assert summary[0]["device_id"] == "d1"

    def test_shutdown(self) -> None:
        mgr = DriverManager()
        d1 = MockDriver(device_id="d1")
        mgr.register(d1)
        mgr.connect("d1")
        mgr.shutdown()
        assert d1.is_connected is False

    def test_connect_failing_driver(self) -> None:
        mgr = DriverManager()
        driver = FailingDriver()
        mgr.register(driver)
        with pytest.raises(DriverError):
            mgr.connect("fail-001")
        assert driver.state == ConnectionState.ERROR

    def test_consecutive_failures(self) -> None:
        mgr = DriverManager()
        driver = MockDriver()
        mgr.register(driver)
        mgr.health_check("mock-001")
        mgr.health_check("mock-001")
        health = mgr.get_device_health("mock-001")
        assert health.consecutive_failures == 0  # MockDriver returns healthy when connected

    def test_read_data_nonexistent(self) -> None:
        mgr = DriverManager()
        with pytest.raises(KeyError):
            mgr.read_data("no-such")

    def test_diagnostics_summary(self) -> None:
        mgr = DriverManager()
        mgr.register(MockDriver(device_id="d1"))
        summary = mgr.get_diagnostics_summary()
        assert "device_count" in summary
