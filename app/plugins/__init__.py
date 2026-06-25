"""Plugin framework for LabLink Platform.

Provides dynamic plugin discovery, loading, lifecycle management,
configuration, health checks, and hot reload capabilities.
"""

from app.plugins.base import BasePlugin, PluginManifest, PluginState
from app.plugins.config import PluginConfigStore
from app.plugins.discovery import PluginDiscovery
from app.plugins.events import (
    PluginActivated,
    PluginDeactivated,
    PluginError,
    PluginEvent,
    PluginLoaded,
    PluginUnloaded,
)
from app.plugins.health import HealthCheckResult, PluginHealthChecker
from app.plugins.loader import PluginLoader
from app.plugins.manager import PluginManager
from app.plugins.registry import PluginRegistry

__all__ = [
    "BasePlugin",
    "HealthCheckResult",
    "PluginActivated",
    "PluginConfigStore",
    "PluginDeactivated",
    "PluginDiscovery",
    "PluginError",
    "PluginEvent",
    "PluginHealthChecker",
    "PluginLoaded",
    "PluginLoader",
    "PluginManager",
    "PluginManifest",
    "PluginRegistry",
    "PluginState",
    "PluginUnloaded",
]
