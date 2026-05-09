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


def test_protocol_aliases_and_macos_global_driver_candidates() -> None:
    director = DeviceOnboardingDirector()
    identity = director.identify_device(DeviceFingerprint(protocol_hint="hl7v2"))
    drivers = director.driver_candidates("macos", identity["protocol"])

    assert identity["protocol"] == "HL7"
    assert any(d["name"] == "HL7/FHIR Bridge Agent" for d in drivers)


def test_connectivity_profile_for_global_and_hybrid_targets() -> None:
    director = DeviceOnboardingDirector()
    global_profile = director.connectivity_profile(
        deployment_target="global",
        region="eu-west",
        max_latency_ms=40,
    )
    hybrid_profile = director.connectivity_profile(
        deployment_target="hybrid",
        region="mena",
        max_latency_ms=15,
    )

    assert global_profile["topology"] == "regional-edge-relay"
    assert hybrid_profile["topology"] == "local-primary-global-failover"


def test_quick_link_profile_supports_non_oem_devices() -> None:
    director = DeviceOnboardingDirector()
    profile = director.quick_link_profile(
        os_name="linux",
        protocol="bluetooth",
        supports_wireless=True,
        is_non_oem=True,
    )

    assert profile["profile"] == "quick-link"
    assert profile["compatibility_mode"] == "extended-generic"
    assert profile["wireless_boost"] is True
