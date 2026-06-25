"""Mindray vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class MindrayVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Mindray"

    @property
    def description(self) -> str:
        return "Mindray in-vitro diagnostics equipment"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="BC-2800",
                description="Automated hematology analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                        "PLT", "LYM%", "MID%", "GRAN%", "LYM#", "MID#",
                        "GRAN#", "RDW-CV", "RDW-SD", "PDW", "MPV", "P-LCR",
                    ),
                ),
                supported_parameters=(
                    "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                    "PLT", "LYM%", "MID%", "GRAN%", "LYM#", "MID#",
                    "GRAN#", "RDW-CV", "RDW-SD", "PDW", "MPV", "P-LCR",
                ),
            ),
            VendorDeviceProfile(
                model="BA-200",
                description="Automated biochemistry analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "ALT", "AST", "ALP", "GGT", "TP", "ALB",
                        "GLU", "BUN", "CRE", "UA", "TC", "TG",
                    ),
                ),
                supported_parameters=(
                    "ALT", "AST", "ALP", "GGT", "TP", "ALB",
                    "GLU", "BUN", "CRE", "UA", "TC", "TG",
                ),
            ),
            VendorDeviceProfile(
                model="CL-1200",
                description="Automated coagulation analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "PT", "APTT", "TT", "FIB", "D-Dimer", "FDP",
                    ),
                ),
                supported_parameters=(
                    "PT", "APTT", "TT", "FIB", "D-Dimer", "FDP",
                ),
            ),
        ]
