"""Unit tests for the Vendor SDK (Phase 3)."""

from __future__ import annotations

import pytest

from app.vendors.base import VendorDeviceProfile, VendorPackage
from app.vendors.builtins import (
    AbbottVendorPackage,
    BeckmanCoulterVendorPackage,
    BioRadVendorPackage,
    MindrayVendorPackage,
    RocheVendorPackage,
    SiemensVendorPackage,
    SysmexVendorPackage,
)
from app.vendors.registry import VendorRegistry

# ── Test Helpers ───────────────────────────────────────────────────


class MinimalVendor(VendorPackage):
    @property
    def vendor_name(self) -> str:
        return "Minimal"

    def supported_models(self) -> list[VendorDeviceProfile]:
        return [
            VendorDeviceProfile(model="M1", description="Basic device"),
        ]


# ── VendorDeviceProfile Tests ──────────────────────────────────────


class TestVendorDeviceProfile:
    def test_creation(self) -> None:
        p = VendorDeviceProfile(model="TestModel", description="A test device")
        assert p.model == "TestModel"
        assert p.protocol == "ASTM"
        assert "tcp" in p.transport
        assert "serial" in p.transport

    def test_frozen(self) -> None:
        p = VendorDeviceProfile(model="M")
        with pytest.raises(AttributeError):
            p.model = "X"  # type: ignore[misc]


# ── VendorPackage Tests ────────────────────────────────────────────


class TestVendorPackage:
    def test_vendor_id(self) -> None:
        pkg = MinimalVendor()
        assert pkg.vendor_id == "minimal"

    def test_supported_models(self) -> None:
        pkg = MinimalVendor()
        models = pkg.supported_models()
        assert len(models) == 1
        assert models[0].model == "M1"

    def test_get_profile(self) -> None:
        pkg = MinimalVendor()
        profile = pkg.get_profile("M1")
        assert profile is not None
        assert profile.model == "M1"

    def test_get_profile_case_insensitive(self) -> None:
        pkg = MinimalVendor()
        profile = pkg.get_profile("m1")
        assert profile is not None

    def test_get_profile_not_found(self) -> None:
        pkg = MinimalVendor()
        assert pkg.get_profile("NONEXISTENT") is None

    def test_create_driver(self) -> None:
        pkg = MinimalVendor()
        driver = pkg.create_driver(device_id="d1", model="M1")
        assert driver.device_id == "d1"
        assert driver.metadata.vendor == "Minimal"
        assert driver.metadata.model == "M1"

    def test_create_driver_unknown_model(self) -> None:
        pkg = MinimalVendor()
        with pytest.raises(ValueError, match="not supported"):
            pkg.create_driver(device_id="d1", model="NONEXISTENT")

    def test_get_adapter_default(self) -> None:
        pkg = MinimalVendor()
        assert pkg.get_adapter() is None

    def test_repr(self) -> None:
        pkg = MinimalVendor()
        r = repr(pkg)
        assert "Minimal" in r
        assert "M1" in r


# ── VendorRegistry Tests ───────────────────────────────────────────


class TestVendorRegistry:
    def test_register_unregister(self) -> None:
        reg = VendorRegistry()
        pkg = MinimalVendor()
        reg.register(pkg)
        assert reg.has("minimal")
        assert reg.count() == 1

        reg.unregister("minimal")
        assert reg.has("minimal") is False

    def test_get_by_name(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        pkg = reg.get_by_name("Minimal")
        assert pkg is not None

    def test_find_model(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        result = reg.find_model("M1")
        assert result is not None
        package, profile = result
        assert package.vendor_name == "Minimal"
        assert profile.model == "M1"

    def test_find_model_not_found(self) -> None:
        reg = VendorRegistry()
        assert reg.find_model("NONEXISTENT") is None

    def test_create_driver(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        driver = reg.create_driver(device_id="d1", vendor="Minimal", model="M1")
        assert driver.device_id == "d1"
        assert driver.metadata.vendor == "Minimal"

    def test_create_driver_unknown_vendor(self) -> None:
        reg = VendorRegistry()
        with pytest.raises(ValueError, match="Unknown vendor"):
            reg.create_driver(device_id="d1", vendor="NoVendor", model="M1")

    def test_create_driver_for_model(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        driver = reg.create_driver_for_model(device_id="d1", model="M1")
        assert driver.metadata.model == "M1"

    def test_create_driver_for_model_unknown(self) -> None:
        reg = VendorRegistry()
        with pytest.raises(ValueError, match="Unknown model"):
            reg.create_driver_for_model(device_id="d1", model="X")

    def test_list_all_models(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        models = reg.list_all_models()
        assert len(models) == 1
        assert models[0]["model"] == "M1"

    def test_summary(self) -> None:
        reg = VendorRegistry()
        reg.register(MinimalVendor())
        s = reg.summary()
        assert len(s) == 1
        assert s[0]["vendor_name"] == "Minimal"


# ── Built-in Vendor Package Tests ──────────────────────────────────


class TestMindrayVendor:
    def test_models(self) -> None:
        pkg = MindrayVendorPackage()
        assert pkg.vendor_name == "Mindray"
        models = pkg.supported_models()
        assert len(models) == 3
        model_names = [m.model for m in models]
        assert "BC-2800" in model_names
        assert "BA-200" in model_names
        assert "CL-1200" in model_names

    def test_create_driver(self) -> None:
        pkg = MindrayVendorPackage()
        driver = pkg.create_driver(device_id="mr1", model="BC-2800")
        assert driver.metadata.vendor == "Mindray"
        assert driver.metadata.model == "BC-2800"

    def test_profile_parameters(self) -> None:
        pkg = MindrayVendorPackage()
        profile = pkg.get_profile("BC-2800")
        assert profile is not None
        assert "WBC" in profile.supported_parameters
        assert "HGB" in profile.supported_parameters


class TestSysmexVendor:
    def test_models(self) -> None:
        pkg = SysmexVendorPackage()
        assert pkg.vendor_name == "Sysmex"
        models = pkg.supported_models()
        assert len(models) == 2
        model_names = [m.model for m in models]
        assert "XN-1000" in model_names

    def test_create_driver(self) -> None:
        pkg = SysmexVendorPackage()
        driver = pkg.create_driver(device_id="sx1", model="XN-1000")
        assert driver.metadata.vendor == "Sysmex"

    def test_xn1000_params(self) -> None:
        pkg = SysmexVendorPackage()
        profile = pkg.get_profile("XN-1000")
        assert profile is not None
        assert "WBC" in profile.supported_parameters
        assert len(profile.supported_parameters) >= 20


class TestAbbottVendor:
    def test_models(self) -> None:
        pkg = AbbottVendorPackage()
        assert pkg.vendor_name == "Abbott"
        models = pkg.supported_models()
        assert len(models) == 2

    def test_alinity_profile(self) -> None:
        pkg = AbbottVendorPackage()
        profile = pkg.get_profile("Alinity s/ ci")
        assert profile is not None
        assert "TSH" in profile.supported_parameters


class TestRocheVendor:
    def test_models(self) -> None:
        pkg = RocheVendorPackage()
        assert pkg.vendor_name == "Roche"
        models = pkg.supported_models()
        assert len(models) == 3

    def test_cobas_molecular(self) -> None:
        pkg = RocheVendorPackage()
        profile = pkg.get_profile("cobas 6800/8800")
        assert profile is not None
        assert "SARS-CoV-2" in profile.supported_parameters


class TestSiemensVendor:
    def test_models(self) -> None:
        pkg = SiemensVendorPackage()
        assert pkg.vendor_name == "Siemens"
        assert len(pkg.supported_models()) == 3

    def test_atellica_ch(self) -> None:
        pkg = SiemensVendorPackage()
        profile = pkg.get_profile("Atellica CH")
        assert profile is not None


class TestBeckmanCoulterVendor:
    def test_models(self) -> None:
        pkg = BeckmanCoulterVendorPackage()
        assert pkg.vendor_name == "Beckman Coulter"
        assert len(pkg.supported_models()) == 3

    def test_dxh800(self) -> None:
        pkg = BeckmanCoulterVendorPackage()
        profile = pkg.get_profile("UniCel DxH 800")
        assert profile is not None


class TestBioRadVendor:
    def test_models(self) -> None:
        pkg = BioRadVendorPackage()
        assert pkg.vendor_name == "Bio-Rad"
        assert len(pkg.supported_models()) == 3

    def test_ih1000(self) -> None:
        pkg = BioRadVendorPackage()
        profile = pkg.get_profile("IH-1000")
        assert profile is not None
        assert "ABO_Rh" in profile.supported_parameters


# ── Integration: Registry + Built-in Vendors ───────────────────────


class TestVendorIntegration:
    def test_register_all_vendors(self) -> None:
        reg = VendorRegistry()
        vendors = [
            MindrayVendorPackage(),
            SysmexVendorPackage(),
            AbbottVendorPackage(),
            RocheVendorPackage(),
            SiemensVendorPackage(),
            BeckmanCoulterVendorPackage(),
            BioRadVendorPackage(),
        ]
        for v in vendors:
            reg.register(v)

        assert reg.count() == 7
        all_models = reg.list_all_models()
        assert len(all_models) >= 19  # 7 vendors, at least 19 models total

    def test_cross_vendor_model_lookup(self) -> None:
        reg = VendorRegistry()
        reg.register(SysmexVendorPackage())
        reg.register(MindrayVendorPackage())

        result = reg.find_model("XN-1000")
        assert result is not None
        assert result[0].vendor_name == "Sysmex"

        result = reg.find_model("BC-2800")
        assert result is not None
        assert result[0].vendor_name == "Mindray"

    def test_auto_detect_vendor_from_model(self) -> None:
        reg = VendorRegistry()
        reg.register(RocheVendorPackage())
        driver = reg.create_driver_for_model(device_id="r1", model="cobas e801")
        assert driver.metadata.vendor == "Roche"
        assert driver.metadata.model == "cobas e801"
