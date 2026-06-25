"""Plugin manager: orchestrates the full plugin lifecycle."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from app.events.base import Event, EventBus
from app.plugins.base import PluginContext, PluginState
from app.plugins.config import PluginConfigStore
from app.plugins.discovery import DiscoveredPlugin, PluginDiscovery
from app.plugins.events import (
    PluginActivated,
    PluginDeactivated,
    PluginError,
    PluginLoaded,
    PluginUnloaded,
)
from app.plugins.health import PluginHealthChecker
from app.plugins.loader import PluginLoader
from app.plugins.registry import PluginRegistry

logger = logging.getLogger(__name__)


class PluginManager:
    """High-level orchestrator for the plugin subsystem.

    Lifecycle:
        discover → load → validate → activate → [health checks] → deactivate → unload

    The manager coordinates discovery, loading, validation, activation,
    health monitoring, hot-reload, and teardown for all plugins.
    """

    def __init__(
        self,
        event_bus: EventBus,
        plugin_dirs: list[str | Path] | None = None,
        module_paths: list[str] | None = None,
        config_path: str | Path = "storage/plugin_config.json",
        platform_version: str = "",
    ) -> None:
        self._event_bus = event_bus
        self._platform_version = platform_version
        self._loader = PluginLoader()
        self._registry = PluginRegistry()
        self._discovery = PluginDiscovery(
            plugin_dirs=plugin_dirs,
            module_paths=module_paths,
        )
        self._config = PluginConfigStore(config_path=config_path)
        self._health = PluginHealthChecker(self._registry)
        self._loaded_modules: dict[str, str] = {}
        self._lock = threading.Lock()
        self._context: PluginContext | None = None
        self._running = False
        self._health_thread: threading.Thread | None = None

    # ── Properties ──────────────────────────────────────────────────

    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    @property
    def config_store(self) -> PluginConfigStore:
        return self._config

    @property
    def health_checker(self) -> PluginHealthChecker:
        return self._health

    # ── Startup / Shutdown ──────────────────────────────────────────

    def startup(self) -> None:
        """Discover, load, validate, and activate all available plugins."""
        self._context = PluginContext(
            event_bus=self._event_bus,
            config_store=self._config,
            platform_version=self._platform_version,
        )
        self._running = True

        discovered = self._discovery.discover_all()
        logger.info("Discovered %d plugin(s), loading...", len(discovered))

        for dp in discovered:
            try:
                self._load_plugin(dp)
            except Exception as exc:
                logger.error("Failed to load plugin '%s': %s", dp.name, exc)

        for name in self._registry.list_all():
            state = self._registry.get_state(name)
            if state == PluginState.LOADED:
                try:
                    self._validate_plugin(name)
                except Exception as exc:
                    logger.error("Failed to validate plugin '%s': %s", name, exc)

        for name in self._registry.list_all():
            state = self._registry.get_state(name)
            if state == PluginState.VALIDATED:
                try:
                    self.activate_plugin(name)
                except Exception as exc:
                    logger.error("Failed to activate plugin '%s': %s", name, exc)

        self._start_health_thread()
        logger.info(
            "Plugin manager started: %d loaded, %d activated",
            len(self._registry.list_by_state(PluginState.LOADED)),
            len(self._registry.list_activated()),
        )

    def shutdown(self) -> None:
        """Deactivate all plugins, stop health checks, tear down."""
        self._running = False
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=5)

        for name in list(self._registry.list_activated()):
            try:
                self.deactivate_plugin(name)
            except Exception as exc:
                logger.error("Failed to deactivate plugin '%s': %s", name, exc)

        for name in list(self._registry.list_all()):
            try:
                self._unload_plugin(name)
            except Exception as exc:
                logger.error("Failed to unload plugin '%s': %s", name, exc)

        logger.info("Plugin manager shut down")

    # ── Discovery ───────────────────────────────────────────────────

    def discover(self) -> list[DiscoveredPlugin]:
        return self._discovery.discover_all()

    def add_plugin_dir(self, path: str | Path) -> None:
        self._discovery.add_plugin_dir(path)

    def add_module_path(self, module_path: str) -> None:
        self._discovery.add_module_path(module_path)

    # ── Individual lifecycle operations ─────────────────────────────

    def _load_plugin(self, dp: DiscoveredPlugin) -> None:
        with self._lock:
            if self._registry.has(dp.name):
                logger.debug("Plugin '%s' already loaded, skipping", dp.name)
                return

        if dp.source_type == "path":
            plugin_cls = self._loader.load_from_path(dp.source)
        elif dp.source_type == "module":
            plugin_cls = self._loader.load_from_module(dp.source)
        elif dp.source_type == "entry_point":
            plugin_cls = self._loader.load_from_module(dp.entry_point)
        else:
            raise ValueError(f"Unknown source type: {dp.source_type}")

        plugin = plugin_cls()
        try:
            plugin.setup()
        except Exception as exc:
            logger.error("Plugin '%s' setup() failed: %s", dp.name, exc)
            raise

        self._registry.register(plugin, module_name=dp.source)
        self._loaded_modules[plugin.name] = dp.source

        self._publish(PluginLoaded(
            plugin_name=plugin.name,
            plugin_version=plugin.version,
        ))

    def _validate_plugin(self, name: str) -> None:
        manifest = self._registry.get_manifest(name)
        if manifest is None:
            raise KeyError(f"Plugin '{name}' not found")

        if manifest.min_platform_version and self._platform_version and self._platform_version < manifest.min_platform_version:
            raise ValueError(
                f"Plugin '{name}' requires platform >= {manifest.min_platform_version}, "
                f"current is {self._platform_version}"
            )

        if manifest.requires:
            for req in manifest.requires:
                if not self._registry.has(req):
                    raise ValueError(f"Plugin '{name}' depends on '{req}' which is not loaded")
                req_state = self._registry.get_state(req)
                if req_state not in (PluginState.ACTIVATED, PluginState.VALIDATED):
                    raise ValueError(
                        f"Plugin '{name}' depends on '{req}' which is in state {req_state.value}"
                    )

        self._registry.set_state(name, PluginState.VALIDATED)

    def activate_plugin(self, name: str) -> None:
        plugin = self._registry.get(name)
        if plugin is None:
            raise KeyError(f"Plugin '{name}' not found")
        if self._registry.get_state(name) != PluginState.VALIDATED:
            raise ValueError(f"Plugin '{name}' is not in validated state")

        manifest = self._registry.get_manifest(name)
        if manifest and manifest.requires:
            for req in manifest.requires:
                if not self._registry.has(req):
                    raise ValueError(f"Plugin '{name}' depends on '{req}' which is not loaded")
                req_state = self._registry.get_state(req)
                if req_state not in (PluginState.ACTIVATED, PluginState.VALIDATED):
                    raise ValueError(
                        f"Plugin '{name}' depends on '{req}' which is in state {req_state.value}"
                    )

        ctx = self._context
        if ctx is None:
            ctx = PluginContext(
                event_bus=self._event_bus,
                config_store=self._config,
                platform_version=self._platform_version,
            )
        try:
            plugin.activate(ctx)
        except Exception as exc:
            self._registry.set_state(name, PluginState.ERROR, error=str(exc))
            self._publish(PluginError(
                plugin_name=name,
                plugin_version=plugin.version,
                error_message=str(exc),
            ))
            raise

        self._registry.set_state(name, PluginState.ACTIVATED)
        self._publish(PluginActivated(
            plugin_name=name,
            plugin_version=plugin.version,
        ))
        logger.info("Activated plugin: %s v%s", name, plugin.version)

    def deactivate_plugin(self, name: str) -> None:
        plugin = self._registry.get(name)
        if plugin is None:
            raise KeyError(f"Plugin '{name}' not found")

        if self._registry.get_state(name) == PluginState.ACTIVATED:
            try:
                plugin.deactivate()
            except Exception as exc:
                logger.error("Plugin '%s' deactivate() failed: %s", name, exc)
            self._registry.set_state(name, PluginState.DEACTIVATED)
            self._publish(PluginDeactivated(
                plugin_name=name,
                plugin_version=plugin.version,
            ))
            logger.info("Deactivated plugin: %s", name)

    def _unload_plugin(self, name: str) -> None:
        plugin = self._registry.get(name)
        if plugin is not None:
            try:
                plugin.teardown()
            except Exception as exc:
                logger.error("Plugin '%s' teardown() failed: %s", name, exc)

        module_name = self._loaded_modules.pop(name, "")
        if module_name:
            self._loader.unload_module(module_name)

        self._registry.unregister(name)
        self._publish(PluginUnloaded(plugin_name=name))

    def load_plugin(self, dp: DiscoveredPlugin) -> None:
        """Public: load, validate, and activate a single discovered plugin."""
        self._load_plugin(dp)
        self._validate_plugin(dp.name)
        self.activate_plugin(dp.name)

    def unload_plugin(self, name: str) -> None:
        """Public: deactivate and unload a single plugin."""
        self.deactivate_plugin(name)
        self._unload_plugin(name)

    # ── Hot reload ──────────────────────────────────────────────────

    def reload_plugin(self, name: str) -> None:
        """Unload and re-load a plugin from the same source."""
        source = self._loaded_modules.get(name)
        if source is None:
            raise KeyError(f"Plugin '{name}' has no tracked source")

        source_type = "path" if source.endswith(".py") else "module"

        self.deactivate_plugin(name)
        self._unload_plugin(name)

        dp = DiscoveredPlugin(name=name, source=source, source_type=source_type)
        self._load_plugin(dp)
        self._validate_plugin(name)
        self.activate_plugin(name)
        logger.info("Reloaded plugin: %s", name)

    # ── Health monitoring ───────────────────────────────────────────

    def _start_health_thread(self) -> None:
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True, name="plugin-health"
        )
        self._health_thread.start()

    def _health_loop(self) -> None:
        while self._running:
            try:
                results = self._health.check_all()
                for r in results:
                    if r.status == "unhealthy":
                        logger.warning(
                            "Plugin '%s' unhealthy: %s", r.plugin_name, r.message
                        )
            except Exception as exc:
                logger.error("Health check loop error: %s", exc)
            time.sleep(30)

    # ── Configuration shortcuts ─────────────────────────────────────

    def get_plugin_config(self, name: str) -> dict[str, Any]:
        return self._config.get_all(name)

    def set_plugin_config(self, name: str, key: str, value: Any) -> None:
        self._config.set(name, key, value)

    # ── Query helpers ───────────────────────────────────────────────

    def summary(self) -> list[dict[str, Any]]:
        return self._registry.summary()

    def capabilities(self) -> dict[str, list[str]]:
        return self._registry.get_capabilities()

    def find_by_capability(self, capability: str) -> list[str]:
        return self._registry.find_by_capability(capability)

    # ── Internal ────────────────────────────────────────────────────

    def _publish(self, event: Event) -> None:
        try:
            self._event_bus.publish(event)
        except Exception as exc:
            logger.debug("Failed to publish plugin event: %s", exc)
