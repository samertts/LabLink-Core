from __future__ import annotations

import logging
import threading
import time

from app.connectors.base import BaseConnector

logger = logging.getLogger("lablink.connection_pool")


class ConnectionPool:
    """Maintains active connectors and retries failed connections."""

    def __init__(self, reconnect_delay_s: float = 2.0) -> None:
        self.reconnect_delay_s = reconnect_delay_s
        self._connectors: dict[str, BaseConnector] = {}
        self._lock = threading.Lock()

    def add(self, connector: BaseConnector) -> None:
        with self._lock:
            self._connectors[connector.connector_id] = connector

        connector.on_disconnect(lambda exc: self._schedule_reconnect(connector, exc))

    def remove(self, connector_id: str) -> None:
        with self._lock:
            connector = self._connectors.pop(connector_id, None)
        if connector:
            connector.disconnect()

    def _schedule_reconnect(self, connector: BaseConnector, exc: BaseException | None) -> None:
        logger.warning("Connector disconnected", extra={"connector_id": connector.connector_id, "error": repr(exc)})

        def _reconnect() -> None:
            time.sleep(self.reconnect_delay_s)
            try:
                connector.connect()
                logger.info("Connector reconnected", extra={"connector_id": connector.connector_id})
            except BaseException as retry_exc:
                logger.exception("Reconnect failed", extra={"connector_id": connector.connector_id, "error": repr(retry_exc)})
                self._schedule_reconnect(connector, retry_exc)

        threading.Thread(target=_reconnect, daemon=True).start()

    def all(self) -> list[BaseConnector]:
        with self._lock:
            return list(self._connectors.values())
