"""Vendor package abstraction: VendorPackage ABC and VendorDeviceProfile."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.adapters.base import DeviceAdapter
from app.drivers.base import BaseDriver, DeviceCapabilities, DeviceMetadata, DriverConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VendorDeviceProfile:
    """Describes a specific device model from a vendor."""

    model: str
    description: str = ""
    protocol: str = "ASTM"
    transport: tuple[str, ...] = ("tcp", "serial")
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    default_config: DriverConfig = field(default_factory=DriverConfig)
    supported_parameters: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class VendorPackage(ABC):
    """Abstract base class for vendor-specific device packages.

    Each vendor (Mindray, Sysmex, Roche, etc.) implements this ABC
    to declare their supported devices, provide driver factories,
    and supply data adapters.

    Vendor packages are loaded by the plugin framework and automatically
    registered with the VendorRegistry.
    """

    @property
    @abstractmethod
    def vendor_name(self) -> str:
        """Canonical vendor name (e.g. ``"Mindray"``, ``"Sysmex"``)."""

    @property
    def vendor_id(self) -> str:
        """Short identifier (defaults to lowercased vendor_name)."""
        return self.vendor_name.lower().replace(" ", "_")

    @property
    def description(self) -> str:
        """Human-readable description of this vendor package."""
        return ""

    @property
    def homepage(self) -> str:
        """Vendor homepage URL."""
        return ""

    @abstractmethod
    def supported_models(self) -> list[VendorDeviceProfile]:
        """Return all device models this vendor package supports."""

    def get_profile(self, model: str) -> VendorDeviceProfile | None:
        """Look up a device profile by model name (case-insensitive)."""
        model_lower = model.lower()
        for profile in self.supported_models():
            if profile.model.lower() == model_lower:
                return profile
        return None

    def create_driver(
        self,
        device_id: str,
        model: str,
        config: DriverConfig | None = None,
    ) -> BaseDriver:
        """Create a driver instance for the given device model.

        Default implementation creates a generic ``BaseDriver``-backed
        instance using the device profile. Subclasses should override
        for vendor-specific driver logic.
        """
        profile = self.get_profile(model)
        if profile is None:
            raise ValueError(
                f"Model '{model}' not supported by {self.vendor_name}. "
                f"Supported: {[p.model for p in self.supported_models()]}"
            )

        metadata = DeviceMetadata(
            device_id=device_id,
            vendor=self.vendor_name,
            model=model,
            protocol=profile.protocol,
            transport=profile.transport[0] if profile.transport else "tcp",
        )
        effective_config = config or profile.default_config

        driver = _GenericVendorDriver(metadata=metadata, config=effective_config)
        return driver

    def get_adapter(self, model: str | None = None) -> DeviceAdapter | None:
        """Return a data adapter for this vendor.

        Override to provide vendor-specific data normalization.
        """
        return None

    def __repr__(self) -> str:
        models = [p.model for p in self.supported_models()]
        return f"<VendorPackage {self.vendor_name} models={models}>"


class _GenericVendorDriver(BaseDriver):
    """Generic driver used when a vendor doesn't provide a custom driver."""

    def connect(self) -> None:
        self._set_state(ConnectionState.CONNECTED)

    def disconnect(self) -> None:
        self._set_state(ConnectionState.DISCONNECTED)

    def read_data(self) -> bytes:
        return b""

    def write_data(self, data: bytes) -> None:
        pass


from app.drivers.base import ConnectionState  # noqa: E402
