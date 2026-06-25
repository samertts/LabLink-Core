"""Tenant store — thread-safe in-memory tenant registry."""

from __future__ import annotations

import threading
from typing import Any

from app.tenancy.models import Tenant


class TenantStore:
    """Thread-safe in-memory store for tenants."""

    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._lock = threading.Lock()

    def get(self, tenant_id: str) -> Tenant | None:
        with self._lock:
            return self._tenants.get(tenant_id)

    def get_by_slug(self, slug: str) -> Tenant | None:
        with self._lock:
            for t in self._tenants.values():
                if t.slug == slug:
                    return t
        return None

    def list_all(self, active_only: bool = False) -> list[Tenant]:
        with self._lock:
            tenants = list(self._tenants.values())
        if active_only:
            tenants = [t for t in tenants if t.is_active]
        return tenants

    def create(self, name: str, slug: str, **kwargs: Any) -> Tenant:
        tenant = Tenant(name=name, slug=slug, **kwargs)
        with self._lock:
            self._tenants[tenant.tenant_id] = tenant
        return tenant

    def update(self, tenant_id: str, **kwargs: Any) -> Tenant | None:
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if tenant is None:
                return None
            for k, v in kwargs.items():
                if hasattr(tenant, k):
                    setattr(tenant, k, v)
            return tenant

    def delete(self, tenant_id: str) -> bool:
        with self._lock:
            if tenant_id in self._tenants:
                del self._tenants[tenant_id]
                return True
            return False

    def count(self, active_only: bool = False) -> int:
        with self._lock:
            if active_only:
                return sum(1 for t in self._tenants.values() if t.is_active)
            return len(self._tenants)


_store: TenantStore | None = None
_store_lock = threading.Lock()


def get_tenant_store() -> TenantStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = TenantStore()
                # Default tenant
                _store.create(name="Default Lab", slug="default", tags=["default"])
    return _store
