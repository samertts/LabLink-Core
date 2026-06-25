"""Device discovery engine: orchestrates scanning, fingerprinting, and recommendation."""
from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from app.discovery.base import DiscoveredDevice, DiscoveryConfig, DiscoveryMethod
from app.discovery.fingerprint import DeviceFingerprint, FingerprintResult
from app.discovery.recommender import DriverRecommendation, DriverRecommender
from app.vendors.registry import VendorRegistry

logger = logging.getLogger(__name__)


class DeviceDiscoveryEngine:
    """Orchestrates device discovery across multiple transports."""

    def __init__(
        self,
        config: DiscoveryConfig | None = None,
        vendor_registry: VendorRegistry | None = None,
    ) -> None:
        self._config = config or DiscoveryConfig()
        self._fingerprint = DeviceFingerprint()
        self._recommender = DriverRecommender(vendor_registry)
        self._discovered: dict[str, DiscoveredDevice] = {}
        self._lock = threading.Lock()

    @property
    def discovered(self) -> list[DiscoveredDevice]:
        with self._lock:
            return list(self._discovered.values())

    def discover_all(self, config: DiscoveryConfig | None = None) -> list[DiscoveredDevice]:
        cfg = config or self._config
        results: list[DiscoveredDevice] = []

        with ThreadPoolExecutor(max_workers=cfg.max_concurrent) as executor:
            futures = []
            futures.append(executor.submit(self._scan_tcp_range, cfg))
            for port_path in cfg.serial_ports:
                futures.append(executor.submit(self._scan_serial, port_path, cfg))

            for future in as_completed(futures):
                try:
                    devices = future.result()
                    results.extend(devices)
                except Exception as exc:
                    logger.error("Discovery scan error: %s", exc)

        with self._lock:
            for device in results:
                self._discovered[device.device_id] = device

        logger.info("Discovered %d device(s)", len(results))
        return results

    def scan_tcp(self, host: str, port: int, timeout: float | None = None) -> DiscoveredDevice | None:
        timeout = timeout or self._config.scan_timeout_seconds
        try:
            start = time.monotonic()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect((host, port))
                elapsed = (time.monotonic() - start) * 1000
                try:
                    sock.settimeout(1.0)
                    sock.sendall(b"\x05")  # ENQ
                    response = sock.recv(1024)
                except Exception:
                    response = b""

                fingerprint = self._fingerprint.identify(response, f"{host}:{port}")
                device_id = f"tcp-{host}-{port}"
                return DiscoveredDevice(
                    device_id=device_id,
                    address=host,
                    port=port,
                    transport="tcp",
                    method=DiscoveryMethod.TCP_SCAN,
                    vendor=fingerprint.vendor,
                    model=fingerprint.model,
                    protocol=fingerprint.protocol,
                    response_time_ms=elapsed,
                    raw_response=response,
                )
        except (TimeoutError, ConnectionRefusedError, OSError):
            return None

    def scan_serial(self, port_path: str, config: DiscoveryConfig | None = None) -> list[DiscoveredDevice]:
        try:
            import serial
            cfg = config or self._config
            with serial.Serial(
                port_path,
                baudrate=9600,
                timeout=cfg.scan_timeout_seconds,
            ) as ser:
                ser.write(b"\x05")
                response = ser.read(1024)
                if response:
                    fingerprint = self._fingerprint.identify(response, port_path)
                    return [DiscoveredDevice(
                        device_id=f"serial-{port_path}",
                        address=port_path,
                        transport="serial",
                        method=DiscoveryMethod.SERIAL_SCAN,
                        vendor=fingerprint.vendor,
                        model=fingerprint.model,
                        protocol=fingerprint.protocol,
                        raw_response=response,
                    )]
        except ImportError:
            logger.debug("pyserial not available, skipping serial scan")
        except Exception as exc:
            logger.debug("Serial scan failed for %s: %s", port_path, exc)
        return []

    def recommend_driver(self, device: DiscoveredDevice) -> DriverRecommendation | None:
        fp = FingerprintResult(
            vendor=device.vendor,
            model=device.model,
            protocol=device.protocol,
            confidence=1.0 if device.vendor != "unknown" else 0.3,
        )
        return self._recommender.recommend(fp)

    def _scan_tcp_range(self, config: DiscoveryConfig) -> list[DiscoveredDevice]:
        results: list[DiscoveredDevice] = []
        try:
            network = ipaddress.ip_network(config.tcp_host_range, strict=False)
            hosts = [str(h) for h in network.hosts()]
        except ValueError:
            hosts = [config.tcp_host_range]

        with ThreadPoolExecutor(max_workers=config.max_concurrent) as executor:
            futures = {}
            for host in hosts:
                for port in config.tcp_ports:
                    future = executor.submit(self.scan_tcp, host, port)
                    futures[future] = (host, port)

            for future in as_completed(futures):
                try:
                    device = future.result()
                    if device:
                        results.append(device)
                except Exception:
                    pass

        return results

    def summary(self) -> dict[str, Any]:
        devices = self.discovered
        vendors = {}
        for d in devices:
            v = d.vendor
            vendors[v] = vendors.get(v, 0) + 1
        return {
            "total": len(devices),
            "by_vendor": vendors,
            "by_transport": {
                "tcp": sum(1 for d in devices if d.transport == "tcp"),
                "serial": sum(1 for d in devices if d.transport == "serial"),
            },
        }
