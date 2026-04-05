import socket
import time

from app.emulator.tcp_device_emulator import EmulatorResult, TCPDeviceEmulator
from app.pipeline.parser_engine import ACK, ENQ, EOT, calculate_checksum


def _collect_until_close(conn: socket.socket) -> bytes:
    data = b""
    while True:
        chunk = conn.recv(1024)
        if not chunk:
            break
        data += chunk
        if chunk.endswith(bytes([EOT])):
            break
    return data


def test_tcp_emulator_handshake_and_stream() -> None:
    emulator = TCPDeviceEmulator(host="127.0.0.1", port=5501)
    emulator.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", 5501), timeout=2) as conn:
        enq = conn.recv(1)
        assert enq and enq[0] == ENQ
        conn.sendall(bytes([ACK]))

        for _ in range(4):
            chunk = conn.recv(512)
            assert b"\x02" in chunk and b"\x03" in chunk
            conn.sendall(bytes([ACK]))

        tail = conn.recv(16)
        assert tail and tail[-1] == EOT

    emulator.stop()


def test_emulator_bad_checksum_mode() -> None:
    emulator = TCPDeviceEmulator(host="127.0.0.1", port=5502, bad_checksum=True)
    emulator.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", 5502), timeout=2) as conn:
        assert conn.recv(1)[0] == ENQ
        conn.sendall(bytes([ACK]))

        # Drain frames and ACK each one.
        frames = []
        for _ in range(4):
            chunk = conn.recv(512)
            frames.append(chunk)
            conn.sendall(bytes([ACK]))

        last_frame = frames[-1]
        etx = last_frame.index(b"\x03")
        payload = last_frame[1:etx]
        received_checksum = last_frame[etx + 1 : etx + 3].decode("ascii")
        assert received_checksum == "00"
        assert calculate_checksum(payload) != received_checksum

    emulator.stop()


def test_emulator_disconnect_after_first_frame() -> None:
    emulator = TCPDeviceEmulator(host="127.0.0.1", port=5503, disconnect_after_first=True)
    emulator.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", 5503), timeout=2) as conn:
        assert conn.recv(1)[0] == ENQ
        conn.sendall(bytes([ACK]))
        first = conn.recv(512)
        assert b"\x02" in first
        conn.sendall(bytes([ACK]))
        tail = conn.recv(32)
        assert tail == b""

    emulator.stop()


def test_emulator_multi_patient_sequence() -> None:
    emulator = TCPDeviceEmulator(
        host="127.0.0.1",
        port=5504,
        results=[
            EmulatorResult("A1", "Alpha^One", "Hb", "11.1", "g/dL"),
            EmulatorResult("B2", "Beta^Two", "Hb", "12.2", "g/dL"),
        ],
    )
    emulator.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", 5504), timeout=2) as conn:
        assert conn.recv(1)[0] == ENQ
        conn.sendall(bytes([ACK]))
        payload_blob = b""
        for _ in range(5):
            chunk = conn.recv(512)
            payload_blob += chunk
            conn.sendall(bytes([ACK]))

        assert b"P|1||A1" in payload_blob
        assert b"P|1||B2" in payload_blob

    emulator.stop()
