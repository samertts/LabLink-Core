"""Plugin registry: tracks all known plugins and their lifecycle states."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Any

from app.plugins.base import BasePlugin, PluginManifest, PluginState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PluginRecord:
    """Internal record for a registered plugin."""

    plugin: BasePlugin
    manifest: PluginManifest
    state: PluginState = PluginState.DISCOVERED
    module_name: str = ""
    error: str | None = None
    activation_count: int = 0


class PluginRegistry:
    """Thread-safe registry of loaded/activated plugins.

    The registry owns the authoritative mapping from plugin name to
    ``PluginRecord`` and exposes query methods for the rest of the
    platform.
    """

    def __init__(self) -> None:
        self._records: dict[str, PluginRecord] = {}
        self._lock = threading.Lock()

    # ── Registration ────────────────────────────────────────────────

    def register(self, plugin: BasePlugin, module_name: str = "") -> None:
        record = PluginRecord(
            plugin=plugin,
            manifest=plugin.manifest,
            state=PluginState.LOADED,
            module_name=module_name,
        )
        with self._lock:
            self._records[plugin.name] = record
        logger.info("Registered plugin: %s v%s", plugin.name, plugin.version)

    def unregister(self, name: str) -> PluginRecord | None:
        with self._lock:
            return self._records.pop(name, None)

    # ── State transitions ───────────────────────────────────────────

    def set_state(self, name: str, state: PluginState, error: str | None = None) -> None:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                raise KeyError(f"Plugin '{name}' not registered")
            record.state = state
            record.error = error
            if state == PluginState.ACTIVATED:
                record.activation_count += 1

    def get_state(self, name: str) -> PluginState:
        with self._lock:
            record = self._records.get(name)
            if record is None:
                raise KeyError(f"Plugin '{name}' not registered")
            return record.state

    # ── Queries ─────────────────────────────────────────────────────

    def get(self, name: str) -> BasePlugin | None:
        with self._lock:
            record = self._records.get(name)
            return record.plugin if record else None

    def get_record(self, name: str) -> PluginRecord | None:
        with self._lock:
            return self._records.get(name)

    def has(self, name: str) -> bool:
        with self._lock:
            return name in self._records

    def list_all(self) -> list[str]:
        with self._lock:
            return list(self._records.keys())

    def list_by_state(self, state: PluginState) -> list[str]:
        with self._lock:
            return [name for name, rec in self._records.items() if rec.state == state]

    def list_activated(self) -> list[str]:
        return self.list_by_state(PluginState.ACTIVATED)

    def get_manifest(self, name: str) -> PluginManifest | None:
        with self._lock:
            record = self._records.get(name)
            return record.manifest if record else None

    def get_capabilities(self) -> dict[str, list[str]]:
        """Return a mapping of plugin name -> list of capabilities."""
        result: dict[str, list[str]] = {}
        with self._lock:
            for name, rec in self._records.items():
                if rec.state == PluginState.ACTIVATED:
                    caps = rec.plugin.capabilities()
                    if caps:
                        result[name] = caps
        return result

    def find_by_capability(self, capability: str) -> list[str]:
        """Find activated plugins that provide *capability*."""
        matches: list[str] = []
        with self._lock:
            for name, rec in self._records.items():
                if rec.state == PluginState.ACTIVATED and capability in rec.plugin.capabilities():
                    matches.append(name)
        return matches

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def summary(self) -> list[dict[str, Any]]:
        """Return a summary list for API responses."""
        with self._lock:
            return [
                {
                    "name": rec.manifest.name,
                    "version": rec.manifest.version,
                    "description": rec.manifest.description,
                    "state": rec.state.value,
                    "error": rec.error,
                    "activation_count": rec.activation_count,
                    "capabilities": rec.plugin.capabilities(),
                }
                for rec in self._records.values()
            ]
