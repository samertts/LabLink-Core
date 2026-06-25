"""Bio-Rad vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class BioRadVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Bio-Rad"

    @property
    def description(self) -> str:
        return "Bio-Rad immunohematology and HbA1c analyzers"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="IH-1000",
                description="Automated immunohematology analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "ABO_Rh", "Antibody_Screen",
                    ),
                ),
                supported_parameters=(
                    "ABO_Rh", "Antibody_Screen",
                ),
            ),
            VendorDeviceProfile(
                model="D-100",
                description="HbA1c analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "HbA1c", "HbF", "HbA2",
                    ),
                ),
                supported_parameters=(
                    "HbA1c", "HbF", "HbA2",
                ),
            ),
            VendorDeviceProfile(
                model="VARIANT II",
                description="HbA1c analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "HbA1c", "HbF",
                    ),
                ),
                supported_parameters=(
                    "HbA1c", "HbF",
                ),
            ),
        ]
