from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass

from app.pipeline.parser_engine import ACK, ENQ, EOT, ETX, STX, calculate_checksum


@dataclass(slots=True)
class EmulatorResult:
    patient_id: str
    patient_name: str
    test_code: str
    value: str
    unit: str


class TCPDeviceEmulator:
    """ASTM TCP emulator: ENQ/ACK handshake + multi-frame + fault injection."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        *,
        results: list[EmulatorResult] | None = None,
        bad_checksum: bool = False,
        disconnect_after_first: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.results = results or [
            EmulatorResult("12345", "Ali^Samer", "Hb", "13.5", "g/dL"),
            EmulatorResult("12345", "Ali^Samer", "WBC", "6.2", "10^9/L"),
        ]
        self.bad_checksum = bad_checksum
        self.disconnect_after_first = disconnect_after_first
        self._server_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._server_socket is not None:
            self._server_socket.close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _serve(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(1)
            server.settimeout(0.5)
            self._server_socket = server

            while not self._stop.is_set():
                try:
                    conn, _addr = server.accept()
                except TimeoutError:
                    continue
                except OSError:
                    break
                with conn:
                    self._handle_client(conn)

    def _handle_client(self, conn: socket.socket) -> None:
        conn.sendall(bytes([ENQ]))
        first = conn.recv(1)
        if not first or first[0] != ACK:
            return

        self.send_results(
            conn,
            self.results,
            bad_checksum=self.bad_checksum,
            disconnect_after_first=self.disconnect_after_first,
        )
        if not self.disconnect_after_first:
            conn.sendall(bytes([EOT]))

    def send_results(
        self,
        conn: socket.socket,
        results: list[EmulatorResult],
        *,
        bad_checksum: bool = False,
        disconnect_after_first: bool = False,
    ) -> None:
        frames: list[bytes] = [self._frame("1H|\\^&|||EMULATOR|||||P|1\r")]

        current_patient = None
        seq = 2
        for result in results:
            if current_patient != result.patient_id:
                current_patient = result.patient_id
                frames.append(self._frame(f"{seq}P|1||{result.patient_id}||{result.patient_name}\r"))
                seq += 1
            frames.append(self._frame(f"{seq}R|1|^^^{result.test_code}|{result.value}|{result.unit}\r"))
            seq += 1

        for idx, frame in enumerate(frames):
            outgoing = frame
            if bad_checksum and idx == len(frames) - 1:
                outgoing = frame[:-4] + b"00\r\n"
            conn.sendall(outgoing)
            ack = conn.recv(1)
            if not ack or ack[0] != ACK:
                return
            if disconnect_after_first and idx == 0:
                conn.close()
                return
            time.sleep(0.05)

    def _frame(self, payload_text: str) -> bytes:
        payload = payload_text.encode("ascii")
        checksum = calculate_checksum(payload).encode("ascii")
        return bytes([STX]) + payload + bytes([ETX]) + checksum + b"\r\n"


if __name__ == "__main__":
    emulator = TCPDeviceEmulator(host="127.0.0.1", port=5000)
    emulator.start()
    print("TCP ASTM emulator running on 127.0.0.1:5000")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        emulator.stop()
