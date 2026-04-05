from __future__ import annotations

import socket
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

DataHandler = Callable[[str], None]
DisconnectHandler = Callable[[BaseException | None], None]


class BaseConnector(ABC):
    """Abstract connector with lifecycle callbacks and safe event emission."""

    def __init__(self, connector_id: str) -> None:
        self.connector_id = connector_id
        self.is_connected = False
        self._data_handlers: list[DataHandler] = []
        self._disconnect_handlers: list[DisconnectHandler] = []

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    def on_data(self, callback: DataHandler) -> None:
        self._data_handlers.append(callback)

    def on_disconnect(self, callback: DisconnectHandler) -> None:
        self._disconnect_handlers.append(callback)

    def _emit_data(self, data: str) -> None:
        for handler in list(self._data_handlers):
            handler(data)

    def _emit_disconnect(self, reason: BaseException | None = None) -> None:
        for handler in list(self._disconnect_handlers):
            handler(reason)


class SerialConnector(BaseConnector):
    """Serial connector with optional polling trigger and resilient reader loop."""

    def __init__(
        self,
        connector_id: str,
        *,
        path: str,
        baudrate: int = 9600,
        encoding: str = "utf-8",
        trigger_command: bytes | None = None,
        trigger_interval_s: float = 0.0,
    ) -> None:
        super().__init__(connector_id)
        self.path = path
        self.baudrate = baudrate
        self.encoding = encoding
        self.trigger_command = trigger_command
        self.trigger_interval_s = trigger_interval_s
        self._stop = threading.Event()
        self._reader_thread: threading.Thread | None = None
        self._trigger_thread: threading.Thread | None = None
        self._serial: Any | None = None

    def connect(self) -> None:
        from serial import Serial  # pyserial; imported lazily for environments without it

        self._serial = Serial(self.path, self.baudrate, timeout=1)
        self._stop.clear()
        self.is_connected = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()
        if self.trigger_command and self.trigger_interval_s > 0:
            self._trigger_thread = threading.Thread(target=self._trigger_loop, daemon=True)
            self._trigger_thread.start()

    def _reader_loop(self) -> None:
        try:
            while not self._stop.is_set() and self._serial:
                chunk = self._serial.read(1024)
                if not chunk:
                    continue
                self._emit_data(chunk.decode(self.encoding, errors="replace"))
        except BaseException as exc:  # resilient: surface error and continue shutdown
            self._emit_disconnect(exc)
        finally:
            self.is_connected = False

    def _trigger_loop(self) -> None:
        while not self._stop.is_set() and self._serial:
            self._serial.write(self.trigger_command or b"")
            time.sleep(self.trigger_interval_s)

    def disconnect(self) -> None:
        self._stop.set()
        if self._serial:
            self._serial.close()
        self.is_connected = False


class TCPConnector(BaseConnector):
    """Persistent TCP socket connector with read loop."""

    def __init__(
        self,
        connector_id: str,
        *,
        host: str,
        port: int,
        encoding: str = "utf-8",
        connect_timeout_s: float = 5.0,
    ) -> None:
        super().__init__(connector_id)
        self.host = host
        self.port = port
        self.encoding = encoding
        self.connect_timeout_s = connect_timeout_s
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._reader_thread: threading.Thread | None = None

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.connect_timeout_s)
        sock.settimeout(1.0)
        self._sock = sock
        self._stop.clear()
        self.is_connected = True
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        try:
            while not self._stop.is_set() and self._sock:
                try:
                    chunk = self._sock.recv(4096)
                except TimeoutError:
                    continue
                if not chunk:
                    raise ConnectionError("TCP connection closed by peer")
                self._emit_data(chunk.decode(self.encoding, errors="replace"))
        except BaseException as exc:
            self._emit_disconnect(exc)
        finally:
            self.is_connected = False

    def disconnect(self) -> None:
        self._stop.set()
        if self._sock:
            self._sock.close()
        self.is_connected = False
