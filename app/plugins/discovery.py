"""Plugin discovery from filesystem directories and Python entry points."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.plugins.loader import PluginLoader

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DiscoveredPlugin:
    """A plugin that has been found but not yet loaded."""

    name: str
    source: str
    source_type: str  # "path" | "module" | "entry_point"
    entry_point: str = ""


class PluginDiscovery:
    """Find available plugins from configured sources.

    Sources:
    - Plugin directories: scan for ``*.py`` files containing ``BasePlugin`` subclasses.
    - Module paths: explicit dotted module paths.
    - Entry points: Python package entry points in a named group.
    """

    DEFAULT_ENTRY_POINT_GROUP = "lablink.plugins"

    def __init__(
        self,
        plugin_dirs: list[str | Path] | None = None,
        module_paths: list[str] | None = None,
        entry_point_group: str | None = None,
    ) -> None:
        self._plugin_dirs = [Path(d) for d in (plugin_dirs or [])]
        self._module_paths = list(module_paths or [])
        self._entry_point_group = entry_point_group or self.DEFAULT_ENTRY_POINT_GROUP
        self._loader = PluginLoader()

    # ── Directory scanning ──────────────────────────────────────────

    def scan_directory(self, directory: Path) -> list[DiscoveredPlugin]:
        """Scan a directory for plugin .py files."""
        discovered: list[DiscoveredPlugin] = []
        if not directory.is_dir():
            logger.warning("Plugin directory does not exist: %s", directory)
            return discovered

        for py_file in sorted(directory.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            discovered.append(
                DiscoveredPlugin(
                    name=py_file.stem,
                    source=str(py_file),
                    source_type="path",
                )
            )

        for sub_dir in sorted(d for d in directory.iterdir() if d.is_dir()):
            init_file = sub_dir / "__init__.py"
            if init_file.exists():
                discovered.append(
                    DiscoveredPlugin(
                        name=sub_dir.name,
                        source=str(sub_dir),
                        source_type="module",
                    )
                )
            else:
                for py_file in sorted(sub_dir.glob("*.py")):
                    if py_file.name.startswith("_"):
                        continue
                    discovered.append(
                        DiscoveredPlugin(
                            name=py_file.stem,
                            source=str(py_file),
                            source_type="path",
                        )
                    )

        return discovered

    # ── Entry point scanning ────────────────────────────────────────

    def scan_entry_points(self) -> list[DiscoveredPlugin]:
        """Discover plugins registered as Python entry points."""
        discovered: list[DiscoveredPlugin] = []
        try:
            if hasattr(__import__("importlib"), "metadata"):
                from importlib.metadata import entry_points

                eps = entry_points()
                if hasattr(eps, "select"):
                    group_eps = eps.select(group=self._entry_point_group)
                else:
                    group_eps = eps.get(self._entry_point_group, [])  # type: ignore[assignment]

                for ep in group_eps:
                    discovered.append(
                        DiscoveredPlugin(
                            name=ep.name,
                            source=ep.value,
                            source_type="entry_point",
                            entry_point=ep.value,
                        )
                    )
        except Exception as exc:
            logger.warning("Failed to scan entry points: %s", exc)
        return discovered

    # ── Combined discovery ──────────────────────────────────────────

    def discover_all(self) -> list[DiscoveredPlugin]:
        """Run all discovery sources and return combined results."""
        all_plugins: list[DiscoveredPlugin] = []
        seen_names: set[str] = set()

        for directory in self._plugin_dirs:
            for plugin in self.scan_directory(directory):
                if plugin.name not in seen_names:
                    all_plugins.append(plugin)
                    seen_names.add(plugin.name)

        for module_path in self._module_paths:
            all_plugins.append(
                DiscoveredPlugin(
                    name=module_path.rsplit(".", 1)[-1],
                    source=module_path,
                    source_type="module",
                )
            )

        for plugin in self.scan_entry_points():
            if plugin.name not in seen_names:
                all_plugins.append(plugin)
                seen_names.add(plugin.name)

        logger.info("Discovered %d plugin(s)", len(all_plugins))
        return all_plugins

    def add_plugin_dir(self, path: str | Path) -> None:
        self._plugin_dirs.append(Path(path))

    def add_module_path(self, module_path: str) -> None:
        self._module_paths.append(module_path)
