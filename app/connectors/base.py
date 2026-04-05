from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


DataHandler = Callable[[str], None]


class DeviceConnector(ABC):
    """Common interface for all device connectors."""

    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def on_data(self, callback: DataHandler) -> None:
        raise NotImplementedError


class SerialConnector(DeviceConnector):
    """MVP placeholder connector; replace with pyserial in production."""

    def __init__(self, port: str, baudrate: int = 9600) -> None:
        self.port = port
        self.baudrate = baudrate
        self._connected = False
        self._callback: DataHandler | None = None

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def on_data(self, callback: DataHandler) -> None:
        self._callback = callback

    def simulate_incoming_data(self, raw_line: str) -> None:
        if self._connected and self._callback:
            self._callback(raw_line)


class TCPConnector(DeviceConnector):
    """Simple TCP connector stub for phase-2 work."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self._callback: DataHandler | None = None

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def on_data(self, callback: DataHandler) -> None:
        self._callback = callback
