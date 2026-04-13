from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class DriverPackage:
    name: str
    os: Literal["windows", "linux"]
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
        )

    def identify_device(self, fingerprint: DeviceFingerprint) -> dict[str, str | float]:
        protocol = (fingerprint.protocol_hint or "ASTM").upper()
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

    def driver_candidates(self, os_name: Literal["windows", "linux"], protocol: str) -> list[dict[str, str]]:
        normalized = protocol.upper()
        matches: list[dict[str, str]] = []
        for package in self._driver_catalog:
            if package.os != os_name:
                continue
            if normalized not in package.supported_protocols and normalized.lower() not in package.supported_protocols:
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

    def install_plan(self, os_name: Literal["windows", "linux"], protocol: str) -> list[str]:
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
            ]
        )
        return steps

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
