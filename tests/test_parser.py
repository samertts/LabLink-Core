from app.parsers.astm_basic import ASTMParseError, parse_astm_result_line


def test_parse_astm_result_line_success() -> None:
    parsed = parse_astm_result_line("|Hb|13.5|g/dL|")
    assert parsed.test_code == "Hb"
    assert parsed.value == 13.5
    assert parsed.unit == "g/dL"


def test_parse_astm_result_line_invalid_value() -> None:
    try:
        parse_astm_result_line("|Hb|abc|g/dL|")
    except ASTMParseError:
        return
    raise AssertionError("ASTMParseError was not raised")
