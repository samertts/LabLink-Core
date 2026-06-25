"""Per-plugin configuration storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PluginConfigStore:
    """Thread-safe per-plugin configuration store.

    Configuration is persisted to a JSON file so it survives restarts.
    Each plugin gets its own namespace keyed by plugin name.
    """

    def __init__(self, config_path: str | Path = "storage/plugin_config.json") -> None:
        self._path = Path(config_path)
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    # ── Persistence ─────────────────────────────────────────────────

    def _load(self) -> None:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self._data = raw
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load plugin config from %s: %s", self._path, exc)
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save plugin config: %s", exc)

    # ── Public API ──────────────────────────────────────────────────

    def get(self, plugin_name: str, key: str, default: Any = None) -> Any:
        return self._data.get(plugin_name, {}).get(key, default)

    def get_all(self, plugin_name: str) -> dict[str, Any]:
        return dict(self._data.get(plugin_name, {}))

    def set(self, plugin_name: str, key: str, value: Any) -> None:
        if plugin_name not in self._data:
            self._data[plugin_name] = {}
        self._data[plugin_name][key] = value
        self._save()

    def set_many(self, plugin_name: str, values: dict[str, Any]) -> None:
        if plugin_name not in self._data:
            self._data[plugin_name] = {}
        self._data[plugin_name].update(values)
        self._save()

    def delete(self, plugin_name: str, key: str) -> bool:
        plugin_cfg = self._data.get(plugin_name)
        if plugin_cfg and key in plugin_cfg:
            del plugin_cfg[key]
            self._save()
            return True
        return False

    def delete_all(self, plugin_name: str) -> bool:
        if plugin_name in self._data:
            del self._data[plugin_name]
            self._save()
            return True
        return False

    def has(self, plugin_name: str, key: str | None = None) -> bool:
        if key is None:
            return plugin_name in self._data
        return key in self._data.get(plugin_name, {})

    def keys(self, plugin_name: str) -> list[str]:
        return list(self._data.get(plugin_name, {}).keys())

    def plugins(self) -> list[str]:
        return list(self._data.keys())
