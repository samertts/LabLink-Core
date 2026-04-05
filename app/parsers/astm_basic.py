from __future__ import annotations

from app.pipeline.parser_engine import ParsedResult
from app.pipeline.parser_engine import ParserEngine as _ParserEngine
from app.pipeline.parser_engine import ParserError as ASTMParseError


def parse_astm_result_line(raw_line: str) -> ParsedResult:
    return _ParserEngine().parse(raw_line)
