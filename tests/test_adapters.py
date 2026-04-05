from app.adapters.registry import AdapterRegistry


def test_adapter_registry_resolves_vendor_specific_adapter() -> None:
    registry = AdapterRegistry()
    adapter = registry.resolve("sysmex")

    rows = adapter.transform_rows(
        [{"patient_id": "1", "test_code": "HGB", "value": "13.1", "unit": "g/dL"}]
    )

    assert rows[0]["test_code"] == "HB"
