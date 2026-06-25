"""Beckman Coulter vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class BeckmanVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Beckman Coulter"

    @property
    def description(self) -> str:
        return "Beckman Coulter clinical chemistry and hematology systems"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="DxC 700 AU",
                description="Automated clinical chemistry analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                        "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                        "Amylase", "Lipase", "Bilirubin", "Ca",
                        "Na", "K", "Cl",
                    ),
                ),
                supported_parameters=(
                    "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                    "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                    "Amylase", "Lipase", "Bilirubin", "Ca",
                    "Na", "K", "Cl",
                ),
            ),
            VendorDeviceProfile(
                model="UniCel DxH 800",
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
                        "RDW-CV", "RDW-SD", "PDW", "MPV",
                        "Retic%", "Retic#", "NRBC%",
                    ),
                ),
                supported_parameters=(
                    "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                    "PLT", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
                    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
                    "RDW-CV", "RDW-SD", "PDW", "MPV",
                    "Retic%", "Retic#", "NRBC%",
                ),
            ),
            VendorDeviceProfile(
                model="Access 2",
                description="Automated immunoassay analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "TSH", "FT4", "Troponin", "BNP", "CRP",
                        "PSA", "Insulin", "Ferritin", "HBsAg",
                        "Cortisol", "Progesterone", "Testosterone",
                        "Estradiol",
                    ),
                ),
                supported_parameters=(
                    "TSH", "FT4", "Troponin", "BNP", "CRP",
                    "PSA", "Insulin", "Ferritin", "HBsAg",
                    "Cortisol", "Progesterone", "Testosterone",
                    "Estradiol",
                ),
            ),
        ]
