import socket
import time

from app.emulator.tcp_device_emulator import TCPDeviceEmulator
from app.pipeline.parser_engine import ACK, ENQ, EOT


def test_tcp_emulator_handshake_and_stream() -> None:
    emulator = TCPDeviceEmulator(host="127.0.0.1", port=5501)
    emulator.start()
    time.sleep(0.1)

    with socket.create_connection(("127.0.0.1", 5501), timeout=2) as conn:
        enq = conn.recv(1)
        assert enq and enq[0] == ENQ

        conn.sendall(bytes([ACK]))

        # Header frame
        chunk = conn.recv(512)
        assert b"\x02" in chunk and b"\x03" in chunk
        conn.sendall(bytes([ACK]))

        # Patient frame
        chunk = conn.recv(512)
        assert b"P|1||12345" in chunk
        conn.sendall(bytes([ACK]))

        # Result frames then EOT
        chunk = conn.recv(512)
        assert b"R|1|^^^Hb" in chunk or b"R|1|^^^WBC" in chunk
        conn.sendall(bytes([ACK]))

        chunk = conn.recv(512)
        assert b"R|1|^^^WBC" in chunk or b"\x04" in chunk
        conn.sendall(bytes([ACK]))

        tail = conn.recv(16)
        assert tail and tail[-1] == EOT

    emulator.stop()
