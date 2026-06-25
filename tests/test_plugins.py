"""Unit tests for the plugin framework (Phase 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.events.base import EventBus
from app.plugins.base import BasePlugin, PluginContext, PluginManifest, PluginState
from app.plugins.config import PluginConfigStore
from app.plugins.discovery import PluginDiscovery
from app.plugins.events import PluginActivated, PluginDeactivated
from app.plugins.health import PluginHealthChecker
from app.plugins.loader import PluginLoader
from app.plugins.manager import PluginManager
from app.plugins.registry import PluginRegistry

# ── Test Plugins ───────────────────────────────────────────────────


class SimplePlugin(BasePlugin):
    _manifest = PluginManifest(
        name="simple-test",
        version="1.0.0",
        description="A simple test plugin",
        author="test",
    )
    activated = False
    deactivated = False
    setup_called = False
    teardown_called = False
    health_data: dict[str, Any] = {"status": "healthy"}

    def setup(self) -> None:
        self.setup_called = True

    def activate(self, ctx: PluginContext) -> None:
        super().activate(ctx)
        self.activated = True

    def deactivate(self) -> None:
        self.deactivated = True

    def teardown(self) -> None:
        self.teardown_called = True

    def health_check(self) -> dict[str, Any]:
        return self.health_data


class DependentPlugin(BasePlugin):
    _manifest = PluginManifest(
        name="dependent-test",
        version="1.0.0",
        requires=["simple-test"],
        provides=["test:dependent"],
    )


class FailingPlugin(BasePlugin):
    _manifest = PluginManifest(
        name="failing-test",
        version="1.0.0",
    )

    def setup(self) -> None:
        raise RuntimeError("Setup failed intentionally")

    def activate(self, ctx: PluginContext) -> None:
        raise RuntimeError("Activate failed intentionally")

    def health_check(self) -> dict[str, Any]:
        return {"status": "unhealthy", "message": "broken"}


class BadHealthPlugin(BasePlugin):
    _manifest = PluginManifest(
        name="bad-health-test",
        version="1.0.0",
    )

    def health_check(self) -> dict[str, Any]:
        raise ValueError("Health check exploded")


# ── PluginManifest Tests ───────────────────────────────────────────


class TestPluginManifest:
    def test_manifest_creation(self) -> None:
        m = PluginManifest(name="test", version="1.0.0")
        assert m.name == "test"
        assert m.version == "1.0.0"
        assert m.requires == []
        assert m.provides == []

    def test_manifest_frozen(self) -> None:
        m = PluginManifest(name="test", version="1.0.0")
        with pytest.raises(AttributeError):
            m.name = "other"  # type: ignore[misc]

    def test_satisfies_dependency(self) -> None:
        m1 = PluginManifest(name="a", version="1.0.0", requires=["b"])
        m2 = PluginManifest(name="b", version="2.0.0")
        assert m1.satisfies_dependency(m2) is True

    def test_satisfies_dependency_missing(self) -> None:
        m1 = PluginManifest(name="a", version="1.0.0", requires=["c"])
        m2 = PluginManifest(name="b", version="2.0.0")
        assert m1.satisfies_dependency(m2) is False

    def test_satisfies_dependency_no_requires(self) -> None:
        m1 = PluginManifest(name="a", version="1.0.0")
        m2 = PluginManifest(name="b", version="2.0.0")
        assert m1.satisfies_dependency(m2) is True


# ── BasePlugin Tests ───────────────────────────────────────────────


class TestBasePlugin:
    def test_simple_plugin_lifecycle(self) -> None:
        plugin = SimplePlugin()
        assert plugin.name == "simple-test"
        assert plugin.version == "1.0.0"
        assert plugin.setup_called is False

        plugin.setup()
        assert plugin.setup_called is True

        ctx = PluginContext(event_bus=EventBus(), config_store=PluginConfigStore())
        plugin.activate(ctx)
        assert plugin.activated is True

        assert plugin.health_check() == {"status": "healthy"}

        plugin.deactivate()
        assert plugin.deactivated is True

        plugin.teardown()
        assert plugin.teardown_called is True

    def test_capabilities(self) -> None:
        plugin = DependentPlugin()
        assert plugin.capabilities() == ["test:dependent"]

    def test_manifest_required(self) -> None:
        class NoManifestPlugin(BasePlugin):
            pass

        plugin = NoManifestPlugin()
        with pytest.raises(NotImplementedError):
            _ = plugin.manifest

    def test_repr(self) -> None:
        plugin = SimplePlugin()
        assert "simple-test" in repr(plugin)
        assert "1.0.0" in repr(plugin)


# ── PluginRegistry Tests ───────────────────────────────────────────


class TestPluginRegistry:
    def test_register_and_get(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        assert reg.get("simple-test") is plugin
        assert reg.has("simple-test") is True

    def test_unregister(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        record = reg.unregister("simple-test")
        assert record is not None
        assert reg.has("simple-test") is False

    def test_state_transitions(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        assert reg.get_state("simple-test") == PluginState.LOADED

        reg.set_state("simple-test", PluginState.VALIDATED)
        assert reg.get_state("simple-test") == PluginState.VALIDATED

        reg.set_state("simple-test", PluginState.ACTIVATED)
        assert reg.get_state("simple-test") == PluginState.ACTIVATED
        assert reg.get_record("simple-test").activation_count == 1

        reg.set_state("simple-test", PluginState.ACTIVATED)
        assert reg.get_record("simple-test").activation_count == 2

    def test_list_by_state(self) -> None:
        reg = PluginRegistry()
        p1, p2 = SimplePlugin(), FailingPlugin()
        reg.register(p1)
        reg.register(p2)
        reg.set_state("simple-test", PluginState.ACTIVATED)
        assert "simple-test" in reg.list_activated()

    def test_capabilities(self) -> None:
        reg = PluginRegistry()
        plugin = DependentPlugin()
        reg.register(plugin)
        reg.set_state("dependent-test", PluginState.ACTIVATED)
        caps = reg.get_capabilities()
        assert "dependent-test" in caps
        assert "test:dependent" in caps["dependent-test"]

    def test_find_by_capability(self) -> None:
        reg = PluginRegistry()
        plugin = DependentPlugin()
        reg.register(plugin)
        reg.set_state("dependent-test", PluginState.ACTIVATED)
        assert "dependent-test" in reg.find_by_capability("test:dependent")
        assert reg.find_by_capability("nonexistent") == []

    def test_summary(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        summary = reg.summary()
        assert len(summary) == 1
        assert summary[0]["name"] == "simple-test"

    def test_count(self) -> None:
        reg = PluginRegistry()
        assert reg.count() == 0
        reg.register(SimplePlugin())
        assert reg.count() == 1


# ── PluginConfigStore Tests ────────────────────────────────────────


class TestPluginConfigStore:
    def test_set_and_get(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("my-plugin", "key1", "value1")
        assert store.get("my-plugin", "key1") == "value1"

    def test_get_all(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p", "a", 1)
        store.set("p", "b", 2)
        assert store.get_all("p") == {"a": 1, "b": 2}

    def test_persistence(self, tmp_path: Path) -> None:
        path = tmp_path / "cfg.json"
        store1 = PluginConfigStore(config_path=path)
        store1.set("p", "k", "v")

        store2 = PluginConfigStore(config_path=path)
        assert store2.get("p", "k") == "v"

    def test_delete(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p", "k", "v")
        assert store.delete("p", "k") is True
        assert store.get("p", "k") is None
        assert store.delete("p", "missing") is False

    def test_delete_all(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p", "a", 1)
        store.set("p", "b", 2)
        assert store.delete_all("p") is True
        assert store.get_all("p") == {}

    def test_has(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p", "k", "v")
        assert store.has("p") is True
        assert store.has("p", "k") is True
        assert store.has("p", "missing") is False
        assert store.has("other") is False

    def test_keys(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p", "a", 1)
        store.set("p", "b", 2)
        assert sorted(store.keys("p")) == ["a", "b"]

    def test_plugins(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set("p1", "k", "v")
        store.set("p2", "k", "v")
        assert sorted(store.plugins()) == ["p1", "p2"]

    def test_set_many(self, tmp_path: Path) -> None:
        store = PluginConfigStore(config_path=tmp_path / "cfg.json")
        store.set_many("p", {"a": 1, "b": 2})
        assert store.get_all("p") == {"a": 1, "b": 2}


# ── PluginLoader Tests ─────────────────────────────────────────────


class TestPluginLoader:
    def test_load_from_path(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(
            "from app.plugins.base import BasePlugin, PluginManifest\n"
            "\n"
            "class TestPlugin(BasePlugin):\n"
            "    _manifest = PluginManifest(name='loaded-test', version='0.1.0')\n"
        )
        loader = PluginLoader()
        cls = loader.load_from_path(plugin_file)
        plugin = cls()
        assert plugin.name == "loaded-test"

    def test_load_nonexistent(self) -> None:
        loader = PluginLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_from_path("/nonexistent/plugin.py")

    def test_load_not_py(self, tmp_path: Path) -> None:
        txt = tmp_path / "plugin.txt"
        txt.write_text("not a plugin")
        loader = PluginLoader()
        with pytest.raises(ValueError):
            loader.load_from_path(txt)

    def test_load_no_plugin_class(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "empty_plugin.py"
        plugin_file.write_text("x = 42\n")
        loader = PluginLoader()
        with pytest.raises(TypeError):
            loader.load_from_path(plugin_file)

    def test_unload_module(self) -> None:
        loader = PluginLoader()
        import sys

        sys.modules["_test_unload"] = type(sys)("fake")
        assert loader.unload_module("_test_unload") is True
        assert loader.unload_module("_test_unload") is False


# ── PluginDiscovery Tests ──────────────────────────────────────────


class TestPluginDiscovery:
    def test_scan_directory(self, tmp_path: Path) -> None:
        (tmp_path / "alpha.py").write_text("# plugin")
        (tmp_path / "beta.py").write_text("# plugin")
        (tmp_path / "_skip.py").write_text("# private")
        (tmp_path / "readme.txt").write_text("# not python")

        disc = PluginDiscovery()
        found = disc.scan_directory(tmp_path)
        names = [p.name for p in found]
        assert "alpha" in names
        assert "beta" in names
        assert "_skip" not in names

    def test_scan_subdirectory_module(self, tmp_path: Path) -> None:
        sub = tmp_path / "my_plugin"
        sub.mkdir()
        (sub / "__init__.py").write_text("x = 1")

        disc = PluginDiscovery()
        found = disc.scan_directory(tmp_path)
        names = [p.name for p in found]
        assert "my_plugin" in names

    def test_scan_nonexistent_dir(self) -> None:
        disc = PluginDiscovery()
        found = disc.scan_directory(Path("/nonexistent"))
        assert found == []

    def test_discover_all_empty(self) -> None:
        disc = PluginDiscovery()
        found = disc.discover_all()
        assert found == []

    def test_discover_all_with_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "plug_a.py").write_text("# a")
        disc = PluginDiscovery(plugin_dirs=[str(tmp_path)])
        found = disc.discover_all()
        assert len(found) == 1
        assert found[0].source_type == "path"

    def test_add_plugin_dir(self, tmp_path: Path) -> None:
        disc = PluginDiscovery()
        disc.add_plugin_dir(tmp_path)
        assert disc._plugin_dirs[0] == tmp_path

    def test_add_module_path(self) -> None:
        disc = PluginDiscovery()
        disc.add_module_path("some.module")
        assert "some.module" in disc._module_paths


# ── PluginHealthChecker Tests ──────────────────────────────────────


class TestPluginHealthChecker:
    def test_check_activated_plugin(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        reg.set_state("simple-test", PluginState.ACTIVATED)

        checker = PluginHealthChecker(reg)
        result = checker.check_plugin("simple-test")
        assert result.status == "healthy"
        assert result.plugin_name == "simple-test"
        assert result.duration_ms >= 0

    def test_check_unactivated_plugin(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)

        checker = PluginHealthChecker(reg)
        result = checker.check_plugin("simple-test")
        assert result.status == "degraded"

    def test_check_nonexistent_plugin(self) -> None:
        reg = PluginRegistry()
        checker = PluginHealthChecker(reg)
        result = checker.check_plugin("no-such-plugin")
        assert result.status == "unhealthy"
        assert "not found" in result.message

    def test_check_all(self) -> None:
        reg = PluginRegistry()
        p1, p2 = SimplePlugin(), FailingPlugin()
        reg.register(p1)
        reg.register(p2)
        reg.set_state("simple-test", PluginState.ACTIVATED)
        reg.set_state("failing-test", PluginState.ACTIVATED)
        p2.health_data = {"status": "healthy"}

        checker = PluginHealthChecker(reg)
        results = checker.check_all()
        assert len(results) == 2

    def test_overall_status_healthy(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        reg.set_state("simple-test", PluginState.ACTIVATED)

        checker = PluginHealthChecker(reg)
        assert checker.get_overall_status() == "healthy"

    def test_overall_status_empty(self) -> None:
        reg = PluginRegistry()
        checker = PluginHealthChecker(reg)
        assert checker.get_overall_status() == "healthy"

    def test_history(self) -> None:
        reg = PluginRegistry()
        plugin = SimplePlugin()
        reg.register(plugin)
        reg.set_state("simple-test", PluginState.ACTIVATED)

        checker = PluginHealthChecker(reg)
        checker.check_plugin("simple-test")
        checker.check_plugin("simple-test")
        history = checker.get_history("simple-test")
        assert len(history) == 2

    def test_exception_in_health_check(self) -> None:
        reg = PluginRegistry()
        plugin = BadHealthPlugin()
        reg.register(plugin)
        reg.set_state("bad-health-test", PluginState.ACTIVATED)

        checker = PluginHealthChecker(reg)
        result = checker.check_plugin("bad-health-test")
        assert result.status == "unhealthy"
        assert "exploded" in result.message


# ── PluginManager Tests ────────────────────────────────────────────


class TestPluginManager:
    def test_startup_shutdown_empty(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        manager.startup()
        assert manager.registry.count() == 0
        manager.shutdown()

    def test_activate_deactivate_plugin(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)

        plugin = SimplePlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("simple-test", PluginState.VALIDATED)

        manager.activate_plugin("simple-test")
        assert manager.registry.get_state("simple-test") == PluginState.ACTIVATED
        assert plugin.activated is True

        manager.deactivate_plugin("simple-test")
        assert manager.registry.get_state("simple-test") == PluginState.DEACTIVATED
        assert plugin.deactivated is True

    def test_activate_nonexistent_plugin(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        with pytest.raises(KeyError):
            manager.activate_plugin("no-such")

    def test_activate_wrong_state(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        plugin = SimplePlugin()
        manager.registry.register(plugin)
        with pytest.raises(ValueError):
            manager.activate_plugin("simple-test")

    def test_events_published(self) -> None:
        bus = EventBus()
        events_received: list[Any] = []
        bus.subscribe("plugin.activated", lambda e: events_received.append(e))
        bus.subscribe("plugin.deactivated", lambda e: events_received.append(e))

        manager = PluginManager(event_bus=bus)
        plugin = SimplePlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("simple-test", PluginState.VALIDATED)

        manager.activate_plugin("simple-test")
        manager.deactivate_plugin("simple-test")

        assert len(events_received) == 2
        assert isinstance(events_received[0], PluginActivated)
        assert isinstance(events_received[1], PluginDeactivated)

    def test_summary_and_capabilities(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        plugin = SimplePlugin()
        manager.registry.register(plugin)

        summary = manager.summary()
        assert len(summary) == 1

    def test_plugin_config(self, tmp_path: Path) -> None:
        bus = EventBus()
        manager = PluginManager(
            event_bus=bus,
            config_path=str(tmp_path / "cfg.json"),
        )
        manager.set_plugin_config("my-plugin", "key", "value")
        assert manager.get_plugin_config("my-plugin") == {"key": "value"}

    def test_find_by_capability(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        plugin = DependentPlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("dependent-test", PluginState.ACTIVATED)

        found = manager.find_by_capability("test:dependent")
        assert "dependent-test" in found

    def test_activate_failing_plugin(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        plugin = FailingPlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("failing-test", PluginState.VALIDATED)

        with pytest.raises(RuntimeError):
            manager.activate_plugin("failing-test")
        assert manager.registry.get_state("failing-test") == PluginState.ERROR

    def test_load_plugin_from_file(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "file_plugin.py"
        plugin_file.write_text(
            "from app.plugins.base import BasePlugin, PluginManifest\n"
            "\n"
            "class FilePlugin(BasePlugin):\n"
            "    _manifest = PluginManifest(name='file-plugin', version='1.0.0')\n"
        )
        bus = EventBus()
        manager = PluginManager(event_bus=bus, plugin_dirs=[str(tmp_path)])
        manager.startup()
        assert manager.registry.has("file-plugin")
        manager.shutdown()

    def test_reload_plugin(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)
        plugin = SimplePlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("simple-test", PluginState.VALIDATED)
        manager.activate_plugin("simple-test")

        # Simulate reload by deactivating and re-registering
        manager.deactivate_plugin("simple-test")
        manager.registry.set_state("simple-test", PluginState.VALIDATED)
        manager.activate_plugin("simple-test")
        assert manager.registry.get_state("simple-test") == PluginState.ACTIVATED

    def test_plugin_dependencies(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)

        p1 = SimplePlugin()
        manager.registry.register(p1)
        manager.registry.set_state("simple-test", PluginState.VALIDATED)
        manager.activate_plugin("simple-test")

        p2 = DependentPlugin()
        manager.registry.register(p2)
        manager.registry.set_state("dependent-test", PluginState.VALIDATED)
        manager.activate_plugin("dependent-test")

        assert manager.registry.get_state("simple-test") == PluginState.ACTIVATED
        assert manager.registry.get_state("dependent-test") == PluginState.ACTIVATED

    def test_activate_plugin_missing_dependency(self) -> None:
        bus = EventBus()
        manager = PluginManager(event_bus=bus)

        plugin = DependentPlugin()
        manager.registry.register(plugin)
        manager.registry.set_state("dependent-test", PluginState.VALIDATED)

        with pytest.raises(ValueError, match="depends on"):
            manager.activate_plugin("dependent-test")
