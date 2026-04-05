from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedResult:
    test_code: str
    value: float
    unit: str


class ASTMParseError(ValueError):
    pass


def parse_astm_result_line(raw_line: str) -> ParsedResult:
    """Parse simplified ASTM-like line: |Hb|13.5|g/dL|"""
    parts = [p for p in raw_line.strip().split("|") if p]
    if len(parts) < 3:
        raise ASTMParseError(f"Invalid ASTM line: {raw_line!r}")

    test_code, value_str, unit = parts[0], parts[1], parts[2]
    try:
        value = float(value_str)
    except ValueError as exc:
        raise ASTMParseError(f"Invalid numeric value: {value_str!r}") from exc

    return ParsedResult(test_code=test_code, value=value, unit=unit)
