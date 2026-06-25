"""Roche vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class RocheVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Roche"

    @property
    def description(self) -> str:
        return "Roche molecular diagnostics and clinical chemistry systems"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="cobas 6800/8800",
                description="Automated molecular diagnostics system",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "SARS-CoV-2", "Influenza_A", "Influenza_B",
                        "RSV", "CT_NG", "HBV", "HCV", "HIV", "CMV",
                    ),
                ),
                supported_parameters=(
                    "SARS-CoV-2", "Influenza_A", "Influenza_B",
                    "RSV", "CT_NG", "HBV", "HCV", "HIV", "CMV",
                ),
            ),
            VendorDeviceProfile(
                model="cobas e801",
                description="Automated immunoassay analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "TSH", "FT4", "Troponin", "BNP", "CRP",
                        "Procalcitonin",
                    ),
                ),
                supported_parameters=(
                    "TSH", "FT4", "Troponin", "BNP", "CRP",
                    "Procalcitonin",
                ),
            ),
            VendorDeviceProfile(
                model="Integra 400",
                description="Clinical chemistry analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                        "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                        "Amylase", "Lipase", "Bilirubin",
                    ),
                ),
                supported_parameters=(
                    "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                    "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                    "Amylase", "Lipase", "Bilirubin",
                ),
            ),
        ]
