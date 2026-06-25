"""Vendor registry: stores and queries vendor packages."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.drivers.base import BaseDriver, DriverConfig
from app.vendors.base import VendorDeviceProfile, VendorPackage

logger = logging.getLogger(__name__)


class VendorRegistry:
    """Central registry for all loaded vendor packages.

    Provides lookup by vendor name, model search, driver creation,
    and aggregated capability queries.
    """

    def __init__(self) -> None:
        self._vendors: dict[str, VendorPackage] = {}
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(self, package: VendorPackage) -> None:
        with self._lock:
            self._vendors[package.vendor_id] = package
        logger.info(
            "Registered vendor: %s (%d models)",
            package.vendor_name,
            len(package.supported_models()),
        )

    def unregister(self, vendor_id: str) -> VendorPackage | None:
        with self._lock:
            return self._vendors.pop(vendor_id, None)

    # ── Lookup ──────────────────────────────────────────────────────

    def get(self, vendor_id: str) -> VendorPackage | None:
        return self._vendors.get(vendor_id)

    def get_by_name(self, name: str) -> VendorPackage | None:
        vid = name.lower().replace(" ", "_")
        return self._vendors.get(vid)

    def has(self, vendor_id: str) -> bool:
        return vendor_id in self._vendors

    def list_all(self) -> list[str]:
        return list(self._vendors.keys())

    def count(self) -> int:
        return len(self._vendors)

    # ── Model search ────────────────────────────────────────────────

    def find_model(self, model: str) -> tuple[VendorPackage, VendorDeviceProfile] | None:
        """Find which vendor supports a given model."""
        for package in self._vendors.values():
            profile = package.get_profile(model)
            if profile is not None:
                return (package, profile)
        return None

    def list_all_models(self) -> list[dict[str, Any]]:
        """List all supported models across all vendors."""
        result = []
        for package in self._vendors.values():
            for profile in package.supported_models():
                result.append({
                    "vendor": package.vendor_name,
                    "vendor_id": package.vendor_id,
                    "model": profile.model,
                    "description": profile.description,
                    "protocol": profile.protocol,
                    "transport": list(profile.transport),
                    "parameters": list(profile.supported_parameters),
                })
        return result

    # ── Driver creation ─────────────────────────────────────────────

    def create_driver(
        self,
        device_id: str,
        vendor: str,
        model: str,
        config: DriverConfig | None = None,
    ) -> BaseDriver:
        """Create a driver instance by vendor and model."""
        package = self.get_by_name(vendor)
        if package is None:
            raise ValueError(f"Unknown vendor: '{vendor}'. Known: {self.list_all()}")
        return package.create_driver(device_id=device_id, model=model, config=config)

    def create_driver_for_model(
        self,
        device_id: str,
        model: str,
        config: DriverConfig | None = None,
    ) -> BaseDriver:
        """Create a driver by model name (auto-detect vendor)."""
        result = self.find_model(model)
        if result is None:
            raise ValueError(f"Unknown model: '{model}'")
        package, _ = result
        return package.create_driver(device_id=device_id, model=model, config=config)

    # ── Summary ─────────────────────────────────────────────────────

    def summary(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "vendor_id": pkg.vendor_id,
                    "vendor_name": pkg.vendor_name,
                    "description": pkg.description,
                    "model_count": len(pkg.supported_models()),
                    "models": [p.model for p in pkg.supported_models()],
                }
                for pkg in self._vendors.values()
            ]
