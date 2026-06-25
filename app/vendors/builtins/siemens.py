"""Siemens vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class SiemensVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Siemens"

    @property
    def description(self) -> str:
        return "Siemens Healthineers clinical chemistry and immunoassay systems"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="Atellica CH",
                description="Clinical chemistry analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                        "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                        "Amylase", "Lipase", "Bilirubin", "Ca", "Na",
                        "K", "Cl", "Mg", "Phos", "Iron",
                    ),
                ),
                supported_parameters=(
                    "ALT", "AST", "ALP", "GGT", "TP", "ALB", "GLU",
                    "BUN", "CRE", "UA", "TC", "TG", "LDH", "CK",
                    "Amylase", "Lipase", "Bilirubin", "Ca", "Na",
                    "K", "Cl", "Mg", "Phos", "Iron",
                ),
            ),
            VendorDeviceProfile(
                model="Atellica IM",
                description="Immunoassay analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "TSH", "FT4", "FT3", "Troponin", "BNP", "CRP",
                        "Procalcitonin", "PSA", "Insulin", "Ferritin",
                        "Cortisol", "Progesterone", "Testosterone",
                        "Estradiol", "Vitamin_B12", "Folate",
                        "HBsAg", "Anti-HCV",
                    ),
                ),
                supported_parameters=(
                    "TSH", "FT4", "FT3", "Troponin", "BNP", "CRP",
                    "Procalcitonin", "PSA", "Insulin", "Ferritin",
                    "Cortisol", "Progesterone", "Testosterone",
                    "Estradiol", "Vitamin_B12", "Folate",
                    "HBsAg", "Anti-HCV",
                ),
            ),
            VendorDeviceProfile(
                model="ADVia 120/2120",
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
        ]
