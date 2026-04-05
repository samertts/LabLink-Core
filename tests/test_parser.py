from app.pipeline.parser_engine import (
    ASTMBuffer,
    ASTMMessageBuilder,
    ASTMParser,
    ParserEngine,
    ParserError,
    calculate_checksum,
    validate_checksum,
)


def build_frame(payload_text: str) -> bytes:
    payload = payload_text.encode("ascii")
    checksum = calculate_checksum(payload).encode("ascii")
    return b"\x02" + payload + b"\x03" + checksum + b"\r\n"


def test_parse_astm_result_line_success() -> None:
    parsed = ParserEngine().parse("|Hb|13.5|g/dL|")
    assert parsed.test_code == "Hb"
    assert parsed.value == 13.5
    assert parsed.unit == "g/dL"


def test_parse_astm_result_line_invalid_value() -> None:
    try:
        ParserEngine().parse("|Hb|abc|g/dL|")
    except ParserError:
        return
    raise AssertionError("ParserError was not raised")


def test_buffer_handles_fragmentation_and_checksum() -> None:
    payload_text = "1H|\\^&|||Device|||||P|1\r2P|1||12345||Doe^John\r3R|1|^^^Hb|13.5|g/dL\r"
    frame = build_frame(payload_text)

    buffer = ASTMBuffer()
    buffer.append(frame[:10])
    assert buffer.extract_frames() == []

    buffer.append(frame[10:])
    extracted = buffer.extract_frames()
    assert len(extracted) == 1

    payload, checksum = extracted[0]
    validate_checksum(payload, checksum)
    parser = ASTMParser()
    records = parser.parse_frame(payload)
    builder = ASTMMessageBuilder()
    results = builder.process_records(records)

    assert len(results) == 1
    assert results[0]["patient_id"] == "12345"
    assert results[0]["test_code"] == "Hb"
    assert results[0]["value"] == "13.5"


def test_checksum_validation_fails_for_tampered_frame() -> None:
    payload = b"1R|1|^^^Hb|13.5|g/dL\r"
    bad_checksum = "00"
    try:
        validate_checksum(payload, bad_checksum)
    except ParserError:
        return
    raise AssertionError("ParserError was not raised for checksum mismatch")
