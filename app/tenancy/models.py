"""Multi-Tenancy — models and configuration."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tenant:
    tenant_id: str = field(default_factory=lambda: f"tnt_{secrets.token_hex(8)}")
    name: str = ""
    slug: str = ""
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    settings: dict[str, Any] = field(default_factory=dict)
    max_devices: int = 50
    max_users: int = 20
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "slug": self.slug,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "settings": self.settings,
            "max_devices": self.max_devices,
            "max_users": self.max_users,
            "tags": self.tags,
        }


@dataclass
class TenantContext:
    """Per-request tenant context attached to the current user."""
    tenant_id: str
    tenant: Tenant | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "tenant": self.tenant.to_dict() if self.tenant else None,
        }
