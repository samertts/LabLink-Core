"""Core plugin types: PluginState, PluginManifest, and BasePlugin ABC."""

from __future__ import annotations

import logging
from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.events.base import EventBus
    from app.plugins.config import PluginConfigStore

logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Lifecycle states of a plugin."""

    DISCOVERED = "discovered"
    LOADED = "loaded"
    VALIDATED = "validated"
    ACTIVATED = "activated"
    DEACTIVATED = "deactivated"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Declarative metadata for a plugin.

    A manifest describes what a plugin provides, what it depends on,
    and how it should be configured. Manifests are read from plugin
    modules via ``BasePlugin.manifest`` or from a JSON/YAML file
    alongside the plugin code.
    """

    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    homepage: str = ""
    requires: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    min_platform_version: str = ""
    max_platform_version: str = ""
    tags: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)

    def satisfies_dependency(self, other: PluginManifest) -> bool:
        """Check if *other* satisfies one of our requirements."""
        if not self.requires:
            return True
        return other.name in self.requires


@dataclass(slots=True)
class PluginContext:
    """Runtime context injected into a plugin on activation.

    Gives plugins access to platform services without tight coupling.
    """

    event_bus: EventBus
    config_store: PluginConfigStore
    platform_version: str = ""
    data_dir: str = ""
    plugin_dir: str = ""

    def get_config(self, plugin_name: str) -> dict[str, Any]:
        return self.config_store.get_all(plugin_name)

    def set_config(self, plugin_name: str, key: str, value: Any) -> None:
        self.config_store.set(plugin_name, key, value)


class BasePlugin(ABC):
    """Abstract base class every plugin must implement.

    Plugins are discovered, loaded, and managed by the ``PluginManager``.
    The lifecycle is:

    1. ``manifest`` is read (class attribute or property).
    2. ``setup()`` is called once after loading (no context yet).
    3. ``activate(ctx)`` is called when the plugin is enabled.
    4. ``health_check()`` is called periodically by the health system.
    5. ``deactivate()`` is called when the plugin is disabled.
    6. ``teardown()`` is called once before unloading.
    """

    _manifest: PluginManifest | None = None

    @property
    def manifest(self) -> PluginManifest:
        """Return the plugin manifest.

        Subclasses may set ``_manifest`` as a class attribute or override
        this property to provide a dynamic manifest.
        """
        if self._manifest is None:
            raise NotImplementedError(
                f"{type(self).__name__} must define a manifest "
                "via _manifest class attribute or by overriding the manifest property."
            )
        return self._manifest

    @property
    def name(self) -> str:
        return self.manifest.name

    @property
    def version(self) -> str:
        return self.manifest.version

    # ── Lifecycle hooks ─────────────────────────────────────────────

    def setup(self) -> None:
        """Called once after the plugin module is imported.

        Use this for one-time initialization that does not require the
        platform context (e.g. validating static resources).
        """

    def activate(self, ctx: PluginContext) -> None:
        """Called when the plugin is enabled.

        Subscribe to events, register connectors/adapters, start
        background tasks, etc. Store *ctx* for later use.
        """
        self._ctx = ctx

    def deactivate(self) -> None:
        """Called when the plugin is disabled.

        Unsubscribe from events, release resources, cancel tasks.
        """

    def teardown(self) -> None:
        """Called once before the plugin module is unloaded.

        Final cleanup — close file handles, release OS resources, etc.
        """

    # ── Health ──────────────────────────────────────────────────────

    def health_check(self) -> dict[str, Any]:
        """Return a health status dict.

        Must contain at least ``{"status": "healthy"|"degraded"|"unhealthy"}``.
        Plugins may add arbitrary keys.
        """
        return {"status": "healthy"}

    # ── Capabilities ────────────────────────────────────────────────

    def capabilities(self) -> list[str]:
        """Return a list of capability strings this plugin provides.

        Examples: ``["connector:bluetooth", "adapter:roche", "protocol:hl7"]``.
        """
        return self.manifest.provides

    def __repr__(self) -> str:
        return f"<Plugin {self.name} v{self.version} [{type(self).__name__}]>"
