"""Abbott vendor package for LabLink Platform."""

from __future__ import annotations

from app.drivers.base import DeviceCapabilities
from app.vendors.base import VendorDeviceProfile, VendorPackage


class AbbottVendorPackage(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Abbott"

    @property
    def description(self) -> str:
        return "Abbott diagnostics immunoassay and hematology systems"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(
                model="Alinity s/ ci",
                description="Automated immunoassay analyzer",
                protocol="ASTM",
                transport=("tcp",),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "TSH", "FT4", "FT3", "anti-TPO", "anti-Tg",
                        "cortisol", "estradiol", "progesterone", "testosterone",
                        "insulin", "ferritin", "B12", "folate", "PSA", "HBsAg",
                    ),
                ),
                supported_parameters=(
                    "TSH", "FT4", "FT3", "anti-TPO", "anti-Tg",
                    "cortisol", "estradiol", "progesterone", "testosterone",
                    "insulin", "ferritin", "B12", "folate", "PSA", "HBsAg",
                ),
            ),
            VendorDeviceProfile(
                model="Cell-Dyn 3700",
                description="Automated hematology analyzer",
                protocol="ASTM",
                transport=("tcp", "serial"),
                capabilities=DeviceCapabilities(
                    supports_realtime=True,
                    supported_protocols=("ASTM",),
                    supported_parameters=(
                        "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                        "PLT", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
                        "NRBC%", "Retic%",
                    ),
                ),
                supported_parameters=(
                    "WBC", "RBC", "HGB", "HCT", "MCV", "MCH", "MCHC",
                    "PLT", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
                    "NRBC%", "Retic%",
                ),
            ),
        ]
