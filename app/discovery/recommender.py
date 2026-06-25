"""Driver recommendation engine based on device fingerprinting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.discovery.fingerprint import FingerprintResult
from app.vendors.registry import VendorRegistry


@dataclass(slots=True)
class DriverRecommendation:
    vendor: str
    model: str
    confidence: float
    protocol: str
    transport: str
    driver_class: str = ""
    reason: str = ""
    alternatives: list[dict[str, Any]] = field(default_factory=list)


class DriverRecommender:
    """Recommends drivers based on device fingerprint and vendor registry."""

    def __init__(self, vendor_registry: VendorRegistry | None = None) -> None:
        self._vendor_registry = vendor_registry

    def recommend(
        self,
        fingerprint: FingerprintResult,
        available_transports: tuple[str, ...] = ("tcp", "serial"),
    ) -> DriverRecommendation | None:
        if fingerprint.vendor == "unknown":
            return None

        if self._vendor_registry:
            pkg = self._vendor_registry.get_by_name(fingerprint.vendor)
            if pkg:
                profile = pkg.get_profile(fingerprint.model)
                if profile:
                    return DriverRecommendation(
                        vendor=fingerprint.vendor,
                        model=fingerprint.model,
                        confidence=fingerprint.confidence,
                        protocol=profile.protocol,
                        transport=profile.transport[0] if profile.transport else "tcp",
                        reason=f"Exact match in vendor registry ({pkg.vendor_name})",
                    )

        return DriverRecommendation(
            vendor=fingerprint.vendor,
            model=fingerprint.model,
            confidence=fingerprint.confidence * 0.7,
            protocol=fingerprint.protocol,
            transport=available_transports[0] if available_transports else "tcp",
            reason="Based on fingerprint pattern match (no registry entry)",
        )

    def recommend_all(
        self,
        fingerprint: FingerprintResult,
        available_transports: tuple[str, ...] = ("tcp", "serial"),
    ) -> list[DriverRecommendation]:
        rec = self.recommend(fingerprint, available_transports)
        results = [rec] if rec else []
        if self._vendor_registry:
            for pkg_name in self._vendor_registry.list_all():
                pkg = self._vendor_registry.get(pkg_name)
                if pkg and pkg.vendor_name != fingerprint.vendor:
                    for profile in pkg.supported_models():
                        if fingerprint.protocol in profile.protocol or profile.protocol in fingerprint.protocol:
                            results.append(DriverRecommendation(
                                vendor=pkg.vendor_name,
                                model=profile.model,
                                confidence=fingerprint.confidence * 0.3,
                                protocol=profile.protocol,
                                transport=profile.transport[0] if profile.transport else "tcp",
                                reason=f"Protocol-compatible alternative ({pkg.vendor_name})",
                            ))
        return results
