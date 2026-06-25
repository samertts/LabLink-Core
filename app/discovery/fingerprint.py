"""Device fingerprinting: identify devices from response patterns."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FingerprintResult:
    vendor: str = "unknown"
    model: str = "unknown"
    protocol: str = "unknown"
    confidence: float = 0.0
    match_patterns: tuple[str, ...] = ()
    details: dict[str, Any] = field(default_factory=dict)


_VENDOR_PATTERNS: list[dict[str, Any]] = [
    {"vendor": "Sysmex", "model": "XN", "patterns": [r"Sysmex", r"XN-\d+"], "protocol": "ASTM"},
    {"vendor": "Sysmex", "model": "KX", "patterns": [r"Sysmex", r"KX-\d+"], "protocol": "ASTM"},
    {"vendor": "Mindray", "model": "BC", "patterns": [r"Mindray", r"BC-\d+"], "protocol": "ASTM"},
    {"vendor": "Mindray", "model": "BA", "patterns": [r"Mindray", r"BA-\d+"], "protocol": "ASTM"},
    {"vendor": "Abbott", "model": "Cell-Dyn", "patterns": [r"Abbott", r"Cell.?Dyn"], "protocol": "ASTM"},
    {"vendor": "Abbott", "model": "Alinity", "patterns": [r"Abbott", r"Alinity"], "protocol": "HL7"},
    {"vendor": "Roche", "model": "cobas", "patterns": [r"[Cc]obas", r"Roche"], "protocol": "HL7"},
    {"vendor": "Roche", "model": "Integra", "patterns": [r"[Ii]ntegra", r"Roche"], "protocol": "ASTM"},
    {"vendor": "Siemens", "model": "Atellica", "patterns": [r"[Ss]iemens", r"Atellica"], "protocol": "HL7"},
    {"vendor": "Siemens", "model": "ADVIA", "patterns": [r"[Ss]iemens", r"ADVIA"], "protocol": "ASTM"},
    {"vendor": "Beckman Coulter", "model": "DxH", "patterns": [r"Beckman", r"DxH"], "protocol": "ASTM"},
    {"vendor": "Beckman Coulter", "model": "DxC", "patterns": [r"Beckman", r"DxC"], "protocol": "ASTM"},
    {"vendor": "Bio-Rad", "model": "IH-1000", "patterns": [r"Bio.?Rad", r"IH-1000"], "protocol": "ASTM"},
]


class DeviceFingerprint:
    """Identifies device vendor, model, and protocol from response data."""

    def __init__(self) -> None:
        self._patterns = _VENDOR_PATTERNS

    def identify(self, data: bytes | str, address: str = "") -> FingerprintResult:
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data

        best_match: FingerprintResult | None = None
        best_confidence = 0.0

        for entry in self._patterns:
            matches = []
            for pattern in entry["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    matches.append(pattern)
            if matches:
                confidence = min(1.0, len(matches) / len(entry["patterns"]))
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = FingerprintResult(
                        vendor=entry["vendor"],
                        model=entry["model"],
                        protocol=entry["protocol"],
                        confidence=confidence,
                        match_patterns=tuple(matches),
                        details={"address": address, "text_preview": text[:200]},
                    )

        return best_match or FingerprintResult(details={"address": address, "raw": text[:200]})

    def detect_protocol(self, data: bytes | str) -> str:
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
        if re.search(r"^MSH\|", text, re.MULTILINE):
            return "HL7"
        if re.search(r"^\d{8,}\r", text) or re.search(r"\rOBR\|", text):
            return "ASTM"
        try:
            import json
            d = json.loads(text)
            if "resourceType" in d:
                return "FHIR"
        except Exception:
            pass
        return "unknown"

    def register_pattern(self, vendor: str, model: str, patterns: list[str], protocol: str = "ASTM") -> None:
        self._patterns.append({
            "vendor": vendor,
            "model": model,
            "patterns": patterns,
            "protocol": protocol,
        })
