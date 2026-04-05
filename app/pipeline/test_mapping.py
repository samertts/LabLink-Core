from __future__ import annotations


class TestMappingEngine:
    """Maps vendor-specific test codes into canonical codes."""

    def __init__(self, mapping: dict[str, str] | None = None) -> None:
        self.mapping = {"HB": "HEMOGLOBIN", "HGB": "HEMOGLOBIN"}
        if mapping:
            self.mapping.update({k.upper(): v for k, v in mapping.items()})

    def canonical_code(self, raw_code: str) -> str:
        normalized = raw_code.upper()
        return self.mapping.get(normalized, normalized)
