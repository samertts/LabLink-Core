from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DriverPackage:
    name: str
    os: Literal["windows", "linux", "macos"]
    install_hint: str
    source: str
    supported_protocols: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceFingerprint:
    vendor_id: str | None = None
    product_id: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    device_class: str | None = None
    protocol_hint: str | None = None


class DeviceOnboardingDirector:
    """Project-level onboarding planner for lab and non-lab devices."""

    def __init__(self) -> None:
        self._driver_catalog: tuple[DriverPackage, ...] = (
            DriverPackage(
                name="Vendor ASTM Bridge Driver",
                os="windows",
                install_hint="pnputil /add-driver *.inf /install",
                source="vendor-portal",
                supported_protocols=("ASTM", "LIS2-A2", "serial", "tcp"),
            ),
            DriverPackage(
                name="Vendor ASTM Bridge Driver",
                os="linux",
                install_hint="install udev rule + restart udev service",
                source="vendor-portal",
                supported_protocols=("ASTM", "LIS2-A2", "serial", "tcp"),
            ),
            DriverPackage(
                name="HL7/FHIR Bridge Agent",
                os="windows",
                install_hint="silent installer MSI + service registration",
                source="lablink-marketplace",
                supported_protocols=("HL7", "FHIR", "tcp", "https"),
            ),
            DriverPackage(
                name="HL7/FHIR Bridge Agent",
                os="linux",
                install_hint="systemd service package install",
                source="lablink-marketplace",
                supported_protocols=("HL7", "FHIR", "tcp", "https"),
            ),
            DriverPackage(
                name="HL7/FHIR Bridge Agent",
                os="macos",
                install_hint="pkg installer + launchd service bootstrap",
                source="lablink-marketplace",
                supported_protocols=("HL7", "FHIR", "tcp", "https"),
            ),
            DriverPackage(
                name="Global Interop Gateway",
                os="windows",
                install_hint="install signed gateway bundle + enable TLS profile",
                source="lablink-marketplace",
                supported_protocols=("ASTM", "HL7", "FHIR", "DICOM", "MQTT", "REST", "https"),
            ),
            DriverPackage(
                name="Global Interop Gateway",
                os="linux",
                install_hint="install signed gateway bundle + enable systemd service",
                source="lablink-marketplace",
                supported_protocols=("ASTM", "HL7", "FHIR", "DICOM", "MQTT", "REST", "https"),
            ),
            DriverPackage(
                name="Global Interop Gateway",
                os="macos",
                install_hint="pkg installer + trust profile activation",
                source="lablink-marketplace",
                supported_protocols=("ASTM", "HL7", "FHIR", "DICOM", "MQTT", "REST", "https"),
            ),
        )
        self._protocol_aliases = {
            "LIS2A2": "ASTM",
            "LIS2-A2": "ASTM",
            "HL7V2": "HL7",
            "HL7-V2": "HL7",
            "FHIR-R4": "FHIR",
            "HTTPS": "REST",
            "HTTP": "REST",
            "BLUETOOTH": "BLE",
            "BLUETOOTH-LE": "BLE",
        }

    def identify_device(self, fingerprint: DeviceFingerprint) -> dict[str, str | float]:
        protocol = self._normalize_protocol(fingerprint.protocol_hint or "ASTM")
        device_class = (fingerprint.device_class or "unknown").lower()
        manufacturer = (fingerprint.manufacturer or "unknown").strip()
        model = (fingerprint.model or "generic").strip()

        score = 0.55
        if fingerprint.vendor_id:
            score += 0.15
        if fingerprint.product_id:
            score += 0.15
        if fingerprint.model:
            score += 0.1

        return {
            "identity": f"{manufacturer}:{model}",
            "protocol": protocol,
            "device_class": device_class,
            "confidence": min(score, 0.98),
        }

    def _normalize_protocol(self, protocol: str) -> str:
        key = protocol.strip().upper()
        return self._protocol_aliases.get(key, key)

    def driver_candidates(self, os_name: Literal["windows", "linux", "macos"], protocol: str) -> list[dict[str, str]]:
        normalized = self._normalize_protocol(protocol)
        matches: list[dict[str, str]] = []
        for package in self._driver_catalog:
            if package.os != os_name:
                continue
            supported = {item.upper() for item in package.supported_protocols}
            if normalized.upper() not in supported:
                continue
            matches.append(
                {
                    "name": package.name,
                    "source": package.source,
                    "install_hint": package.install_hint,
                }
            )
        if not matches:
            matches.append(
                {
                    "name": "Generic Network Device Driver",
                    "source": "os-default",
                    "install_hint": "use operating system default signed drivers",
                }
            )
        return matches

    def quick_link_profile(
        self,
        *,
        os_name: Literal["windows", "linux", "macos"],
        protocol: str,
        supports_wireless: bool,
        is_non_oem: bool = False,
    ) -> dict[str, str | bool | int]:
        normalized = self._normalize_protocol(protocol)
        fast_drivers = self.driver_candidates(os_name, normalized)
        compatibility_mode = "strict-oem"
        if is_non_oem:
            compatibility_mode = "extended-generic"
            if not any(d["source"] == "os-default" for d in fast_drivers):
                fast_drivers.append(
                    {
                        "name": "Generic Compatibility Bridge",
                        "source": "os-default",
                        "install_hint": "use default signed OS driver + compatibility profile",
                    }
                )

        wireless_boost = supports_wireless and normalized in {"ASTM", "HL7", "FHIR", "REST", "BLE"}
        return {
            "profile": "quick-link",
            "compatibility_mode": compatibility_mode,
            "zero_touch_pairing": True,
            "wireless_boost": wireless_boost,
            "recommended_poll_interval_ms": 300 if wireless_boost else 500,
            "driver_count": len(fast_drivers),
        }

    def install_plan(self, os_name: Literal["windows", "linux", "macos"], protocol: str) -> list[str]:
        candidates = self.driver_candidates(os_name=os_name, protocol=protocol)
        steps = [
            "Capture hardware fingerprint (VID/PID, serial number, firmware version)",
            "Validate digital signature and hash for every driver package",
        ]
        for candidate in candidates:
            steps.append(f"Install {candidate['name']} via: {candidate['install_hint']}")
        steps.extend(
            [
                "Run loopback ASTM/HL7 handshake validation",
                "Bind device to LabLink policy profile and enable telemetry",
                "Run interoperability checks for local LIS and global cloud APIs (FHIR/REST)",
            ]
        )
        return steps

    def connectivity_profile(
        self,
        *,
        deployment_target: Literal["local", "global", "hybrid"],
        region: str,
        max_latency_ms: int,
    ) -> dict[str, str | int]:
        if deployment_target == "local":
            return {
                "topology": "direct-lan",
                "security": "mutual-tls-optional",
                "optimization": "persistent sockets + local DNS cache",
                "region": region,
                "target_rtt_ms": min(max_latency_ms, 10),
            }
        if deployment_target == "global":
            return {
                "topology": "regional-edge-relay",
                "security": "mutual-tls-required",
                "optimization": "nearest-region routing + connection pooling",
                "region": region,
                "target_rtt_ms": max(20, max_latency_ms),
            }
        return {
            "topology": "local-primary-global-failover",
            "security": "mutual-tls-required",
            "optimization": "active health checks + fast failover",
            "region": region,
            "target_rtt_ms": max(15, max_latency_ms),
        }

    def recommend_transport(
        self,
        *,
        supports_wireless: bool,
        required_mbps: int,
        max_latency_ms: int,
        distance_meters: int,
    ) -> dict[str, str | int]:
        if required_mbps >= 500 or max_latency_ms <= 5:
            return {
                "mode": "wired",
                "technology": "ethernet-1g",
                "expected_mbps": 940,
                "reason": "best deterministic throughput and latency",
            }

        if supports_wireless and required_mbps >= 120:
            return {
                "mode": "wireless",
                "technology": "wifi-6e",
                "expected_mbps": 600,
                "reason": "high throughput with enterprise roaming",
            }

        if supports_wireless and distance_meters <= 20:
            return {
                "mode": "wireless",
                "technology": "wifi-6",
                "expected_mbps": 250,
                "reason": "fast enough for analyzers and bedside devices",
            }

        return {
            "mode": "wired",
            "technology": "usb-3",
            "expected_mbps": 300,
            "reason": "stable fallback with plug-and-play deployment",
        }
