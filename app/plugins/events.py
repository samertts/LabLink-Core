"""Plugin domain events published on the platform EventBus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.events.base import Event


@dataclass(slots=True)
class PluginEvent(Event):
    """Base event for all plugin lifecycle events."""

    event_type: str = "plugin.event"
    plugin_name: str = ""
    plugin_version: str = ""


@dataclass(slots=True)
class PluginLoaded(PluginEvent):
    event_type: str = "plugin.loaded"


@dataclass(slots=True)
class PluginActivated(PluginEvent):
    event_type: str = "plugin.activated"


@dataclass(slots=True)
class PluginDeactivated(PluginEvent):
    event_type: str = "plugin.deactivated"


@dataclass(slots=True)
class PluginUnloaded(PluginEvent):
    event_type: str = "plugin.unloaded"


@dataclass(slots=True)
class PluginError(PluginEvent):
    event_type: str = "plugin.error"
    error_message: str = ""
    error_details: dict[str, Any] = field(default_factory=dict)
