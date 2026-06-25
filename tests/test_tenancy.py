"""Tests for Multi-Tenancy — tenant store, models, isolation (Phase 9)."""

from __future__ import annotations

from app.tenancy.models import Tenant, TenantContext
from app.tenancy.store import TenantStore, get_tenant_store

# ── Tenant Model Tests ─────────────────────────────────────────────


class TestTenant:
    def test_creation(self) -> None:
        t = Tenant(name="Lab A", slug="lab-a")
        assert t.name == "Lab A"
        assert t.slug == "lab-a"
        assert t.is_active is True

    def test_to_dict(self) -> None:
        t = Tenant(name="Lab A", slug="lab-a", max_devices=100)
        d = t.to_dict()
        assert d["name"] == "Lab A"
        assert d["max_devices"] == 100
        assert d["is_active"] is True

    def test_tenant_context(self) -> None:
        t = Tenant(name="Lab A", slug="lab-a")
        ctx = TenantContext(tenant_id=t.tenant_id, tenant=t)
        d = ctx.to_dict()
        assert d["tenant_id"] == t.tenant_id
        assert d["tenant"]["name"] == "Lab A"


# ── TenantStore Tests ─────────────────────────────────────────────


class TestTenantStore:
    def test_create_and_get(self) -> None:
        store = TenantStore()
        t = store.create("Lab A", "lab-a")
        assert store.get(t.tenant_id) is not None
        assert store.get(t.tenant_id).name == "Lab A"

    def test_get_by_slug(self) -> None:
        store = TenantStore()
        store.create("Lab A", "lab-a")
        assert store.get_by_slug("lab-a") is not None
        assert store.get_by_slug("nonexistent") is None

    def test_list_all(self) -> None:
        store = TenantStore()
        store.create("Lab A", "lab-a")
        store.create("Lab B", "lab-b")
        assert len(store.list_all()) == 2

    def test_list_active_only(self) -> None:
        store = TenantStore()
        t1 = store.create("Lab A", "lab-a")
        store.create("Lab B", "lab-b")
        store.update(t1.tenant_id, is_active=False)
        assert len(store.list_all(active_only=True)) == 1

    def test_update(self) -> None:
        store = TenantStore()
        t = store.create("Lab A", "lab-a")
        store.update(t.tenant_id, name="Lab A Updated")
        updated = store.get(t.tenant_id)
        assert updated is not None
        assert updated.name == "Lab A Updated"

    def test_delete(self) -> None:
        store = TenantStore()
        t = store.create("Lab A", "lab-a")
        assert store.delete(t.tenant_id) is True
        assert store.get(t.tenant_id) is None
        assert store.delete("nonexistent") is False

    def test_count(self) -> None:
        store = TenantStore()
        store.create("A", "a")
        store.create("B", "b")
        assert store.count() == 2

    def test_default_tenant(self) -> None:
        store = get_tenant_store()
        default = store.get_by_slug("default")
        assert default is not None
        assert default.name == "Default Lab"


# ── Default Tenant Tests ───────────────────────────────────────────


class TestDefaultTenant:
    def test_default_tenant_exists(self) -> None:
        store = get_tenant_store()
        assert store.count() >= 1
        default = store.get_by_slug("default")
        assert default is not None

    def test_default_tenant_is_active(self) -> None:
        store = get_tenant_store()
        default = store.get_by_slug("default")
        assert default is not None
        assert default.is_active is True
