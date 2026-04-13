from app.core.device_onboarding import DeviceFingerprint, DeviceOnboardingDirector


def test_identify_device_confidence_increases_with_fingerprint() -> None:
    director = DeviceOnboardingDirector()

    generic = director.identify_device(DeviceFingerprint(protocol_hint="astm"))
    specific = director.identify_device(
        DeviceFingerprint(
            vendor_id="0ABC",
            product_id="00FE",
            manufacturer="Sysmex",
            model="XN-1000",
            protocol_hint="astm",
        )
    )

    assert generic["protocol"] == "ASTM"
    assert float(specific["confidence"]) > float(generic["confidence"])


def test_driver_candidates_fallback_for_unknown_protocol() -> None:
    director = DeviceOnboardingDirector()
    drivers = director.driver_candidates("linux", "modbus")

    assert drivers[0]["name"] == "Generic Network Device Driver"


def test_recommend_transport_for_low_latency_prefers_wired() -> None:
    director = DeviceOnboardingDirector()
    recommendation = director.recommend_transport(
        supports_wireless=True,
        required_mbps=100,
        max_latency_ms=4,
        distance_meters=10,
    )

    assert recommendation["mode"] == "wired"
    assert recommendation["technology"] == "ethernet-1g"
