from __future__ import annotations

from dataclasses import dataclass, field

from app.parsers.astm_basic import ASTMParseError, ParsedResult


@dataclass(slots=True)
class StreamBuffer:
    pending: str = ""
    delimiter: str = "\n"


@dataclass(slots=True)
class ParserEngine:
    """Stateful parser that handles fragmented incoming streams."""

    buffer: StreamBuffer = field(default_factory=StreamBuffer)

    def feed(self, chunk: str) -> list[ParsedResult]:
        self.buffer.pending += chunk
        lines: list[str] = []
        while True:
            idx = self.buffer.pending.find(self.buffer.delimiter)
            if idx == -1:
                break
            lines.append(self.buffer.pending[:idx].strip("\r"))
            self.buffer.pending = self.buffer.pending[idx + len(self.buffer.delimiter) :]

        results: list[ParsedResult] = []
        for line in lines:
            if not line:
                continue
            parsed = self._parse_line_state_machine(line)
            results.append(parsed)
        return results

    def _parse_line_state_machine(self, line: str) -> ParsedResult:
        """Minimal AST-like state machine parser (not split-based)."""
        fields: list[str] = []
        current: list[str] = []
        started = False

        for ch in line:
            if ch == "|":
                if not started:
                    started = True
                    continue
                fields.append("".join(current))
                current = []
                continue
            if started:
                current.append(ch)

        fields = [f for f in fields if f != ""]
        if len(fields) < 3:
            raise ASTMParseError(f"Invalid ASTM record: {line!r}")

        test_code = fields[0]
        try:
            value = float(fields[1])
        except ValueError as exc:
            raise ASTMParseError(f"Invalid numeric value: {fields[1]!r}") from exc

        return ParsedResult(test_code=test_code, value=value, unit=fields[2])
