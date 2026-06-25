"""Sysmex vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class SysmexVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Sysmex"

    @property
    def description(self) -> str:
        return "Sysmex hematology and body fluid analyzers"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="XN-1000",
                description="Automated hematology analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                        "PLT", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
                        "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
                        "IRF", "LFR", "MFR", "HFR", "RBC-O", "HGB-O",
                        "PLT-F", "RET%", "RET#", "PLT-I", "RBC-Info",
                    ),
                ),
                supported_parameters=(
                    "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                    "PLT", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
                    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
                    "IRF", "LFR", "MFR", "HFR", "RBC-O", "HGB-O",
                    "PLT-F", "RET%", "RET#", "PLT-I", "RBC-Info",
                ),
            ),
            VendorDeviceProfile(
                model="XN-310",
                description="Body fluid analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "WBC", "RBC", "PMN", "MN", "EC", "TC",
                        "neut%", "lymph%",
                    ),
                ),
                supported_parameters=(
                    "WBC", "RBC", "PMN", "MN", "EC", "TC",
                    "neut%", "lymph%",
                ),
            ),
        ]
