from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
import socket
import threading
import time

from app.pipeline.parser_engine import ACK, ENQ, EOT

DataHandler = Callable[[bytes], None]

logger = logging.getLogger("lablink.connectors")


class BaseConnector(ABC):
    """Abstract connector contract used by all device transports."""

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.is_connected = False
        self._callback: DataHandler | None = None

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    def on_data(self, callback: DataHandler) -> None:
        self._callback = callback

    def _emit_data(self, data: bytes) -> None:
        if self._callback is not None:
            self._callback(data)


class SerialConnector(BaseConnector):
    """Serial connector with ASTM handshake support (ENQ/ACK/EOT)."""

    def __init__(
        self,
        *,
        device_id: str,
        path: str,
        baudrate: int = 9600,
    ) -> None:
        super().__init__(device_id=device_id)
        self.path = path
        self.baudrate = baudrate
        self._port = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def connect(self) -> None:
        if self.is_connected:
            return

        from serial import Serial  # pyserial runtime dependency

        self._port = Serial(self.path, self.baudrate, timeout=1)
        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self.is_connected = True
        logger.info("Serial connected", extra={"device_id": self.device_id, "path": self.path})

    def _read_loop(self) -> None:
        while not self._stop_event.is_set() and self._port is not None:
            try:
                chunk: bytes = self._port.read(1024)
                if not chunk:
                    continue

                if len(chunk) == 1 and chunk[0] == ENQ:
                    self._port.write(bytes([ACK]))
                    logger.debug("ENQ received; ACK sent", extra={"device_id": self.device_id})
                    continue

                if len(chunk) == 1 and chunk[0] == EOT:
                    logger.debug("EOT received", extra={"device_id": self.device_id})
                    continue

                self._emit_data(chunk)
            except Exception:
                logger.exception("Serial read loop failed", extra={"device_id": self.device_id})
                self.is_connected = False
                break

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
        if self._port is not None:
            self._port.close()
        self.is_connected = False
        logger.info("Serial disconnected", extra={"device_id": self.device_id})


class TCPConnector(BaseConnector):
    """TCP connector with automatic reconnect and safe no-crash behavior."""

    def __init__(
        self,
        *,
        device_id: str,
        host: str,
        port: int,
        reconnect_delay_seconds: float = 1.0,
    ) -> None:
        super().__init__(device_id=device_id)
        self.host = host
        self.port = port
        self.reconnect_delay_seconds = reconnect_delay_seconds
        self._socket: socket.socket | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def connect(self) -> None:
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._run_forever, daemon=True)
        self._reader_thread.start()

    def _run_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=5) as conn:
                    self._socket = conn
                    self.is_connected = True
                    logger.info(
                        "TCP connected",
                        extra={"device_id": self.device_id, "host": self.host, "port": self.port},
                    )
                    while not self._stop_event.is_set():
                        data = conn.recv(4096)
                        if not data:
                            raise ConnectionError("Remote peer closed connection")
                        self._emit_data(data)
            except Exception as exc:
                self.is_connected = False
                logger.warning(
                    "TCP connection dropped; retrying",
                    extra={
                        "device_id": self.device_id,
                        "host": self.host,
                        "port": self.port,
                        "error": str(exc),
                    },
                )
                time.sleep(self.reconnect_delay_seconds)

    def disconnect(self) -> None:
        self._stop_event.set()
        if self._socket is not None:
            self._socket.close()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
        self.is_connected = False
        logger.info("TCP disconnected", extra={"device_id": self.device_id})
