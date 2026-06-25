"""Dynamic plugin loading via importlib."""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
import types
from pathlib import Path

from app.plugins.base import BasePlugin

logger = logging.getLogger(__name__)

# Subpackage of BasePlugin we expose as public attributes.
_PLUGIN_ATTR = "BasePlugin"


def _find_plugin_class(module: types.ModuleType) -> type[BasePlugin] | None:
    """Inspect a loaded module for a BasePlugin subclass."""
    for attr_name in dir(module):
        obj = getattr(module, attr_name, None)
        if (
            obj is not None
            and isinstance(obj, type)
            and issubclass(obj, BasePlugin)
            and obj is not BasePlugin
        ):
            return obj
    return None


class PluginLoader:
    """Load plugin modules from filesystem paths or entry-point strings.

    Supported source formats:

    - Absolute or relative filesystem path to a ``.py`` file.
    - Dotted module path (e.g. ``my_plugin``) that is already importable.
    """

    def load_from_path(self, path: str | Path) -> type[BasePlugin]:
        """Load a plugin class from a filesystem path to a .py file."""
        file_path = Path(path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"Plugin file not found: {file_path}")
        if not file_path.suffix == ".py":
            raise ValueError(f"Plugin file must be a .py file: {file_path}")

        module_name = f"_lablink_plugin_{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise ImportError(f"Failed to execute plugin module {file_path}: {exc}") from exc

        plugin_cls = _find_plugin_class(module)
        if plugin_cls is None:
            raise TypeError(f"No BasePlugin subclass found in {file_path}")
        return plugin_cls

    def load_from_module(self, module_path: str) -> type[BasePlugin]:
        """Load a plugin class from a dotted module path (e.g. ``my_package.my_plugin``)."""
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(f"Cannot import plugin module '{module_path}': {exc}") from exc

        plugin_cls = _find_plugin_class(module)
        if plugin_cls is None:
            raise TypeError(f"No BasePlugin subclass found in module '{module_path}'")
        return plugin_cls

    def unload_module(self, module_name: str) -> bool:
        """Remove a module from sys.modules to allow re-import."""
        if module_name in sys.modules:
            del sys.modules[module_name]
            return True
        return False
