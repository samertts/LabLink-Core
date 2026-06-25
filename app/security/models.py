"""RBAC models: User, Role, Permission, and in-memory store."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Permission(str, Enum):
    """Granular permission flags."""

    # Device management
    DEVICE_READ = "device:read"
    DEVICE_WRITE = "device:write"
    DEVICE_DELETE = "device:delete"

    # Results / data
    RESULT_READ = "result:read"
    RESULT_WRITE = "result:write"
    RESULT_DELETE = "result:delete"

    # Driver management
    DRIVER_READ = "driver:read"
    DRIVER_INSTALL = "driver:install"
    DRIVER_UNINSTALL = "driver:uninstall"

    # Plugin management
    PLUGIN_READ = "plugin:read"
    PLUGIN_INSTALL = "plugin:install"
    PLUGIN_UNINSTALL = "plugin:uninstall"

    # Vendor packages
    VENDOR_READ = "vendor:read"
    VENDOR_INSTALL = "vendor:install"

    # Protocol management
    PROTOCOL_READ = "protocol:read"
    PROTOCOL_WRITE = "protocol:write"

    # Discovery
    DISCOVERY_READ = "discovery:read"
    DISCOVERY_SCAN = "discovery:scan"

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"

    # Role management
    ROLE_READ = "role:read"
    ROLE_WRITE = "role:write"

    # Audit
    AUDIT_READ = "audit:read"

    # System
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_CONFIG = "system:config"

    # API key management
    APIKEY_READ = "apikey:read"
    APIKEY_WRITE = "apikey:write"
    APIKEY_DELETE = "apikey:delete"


# ── Predefined Roles ───────────────────────────────────────────────

class RoleName(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


VIEWER_PERMISSIONS: frozenset[Permission] = frozenset({
    Permission.DEVICE_READ,
    Permission.RESULT_READ,
    Permission.DRIVER_READ,
    Permission.PLUGIN_READ,
    Permission.VENDOR_READ,
    Permission.PROTOCOL_READ,
    Permission.DISCOVERY_READ,
})

OPERATOR_PERMISSIONS: frozenset[Permission] = VIEWER_PERMISSIONS | frozenset({
    Permission.DEVICE_WRITE,
    Permission.RESULT_WRITE,
    Permission.DRIVER_INSTALL,
    Permission.PLUGIN_INSTALL,
    Permission.VENDOR_INSTALL,
    Permission.PROTOCOL_WRITE,
    Permission.DISCOVERY_SCAN,
})

ADMIN_PERMISSIONS: frozenset[Permission] = frozenset(Permission)

_DEFAULT_ROLE_PERMISSIONS: dict[RoleName, frozenset[Permission]] = {
    RoleName.VIEWER: VIEWER_PERMISSIONS,
    RoleName.OPERATOR: OPERATOR_PERMISSIONS,
    RoleName.ADMIN: ADMIN_PERMISSIONS,
}


# ── Data Classes ───────────────────────────────────────────────────

@dataclass
class Role:
    name: str
    permissions: frozenset[Permission]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "permissions": sorted(p.value for p in self.permissions),
            "description": self.description,
        }


@dataclass
class User:
    user_id: str
    username: str
    hashed_password: str
    roles: list[str] = field(default_factory=lambda: ["viewer"])
    tenant_id: str = "default"
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    last_login: float | None = None
    failed_login_attempts: int = 0
    locked_until: float | None = None

    def to_dict(self, *, include_password: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "user_id": self.user_id,
            "username": self.username,
            "roles": self.roles,
            "tenant_id": self.tenant_id,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "failed_login_attempts": self.failed_login_attempts,
            "locked_until": self.locked_until,
        }
        if include_password:
            d["hashed_password"] = self.hashed_password
        return d


@dataclass
class APIKey:
    key_id: str
    key_prefix: str
    key_hash: str
    user_id: str
    name: str = ""
    scopes: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    last_used: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "name": self.name,
            "scopes": self.scopes,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used": self.last_used,
        }


# ── In-Memory Store ────────────────────────────────────────────────

class SecurityStore:
    """Thread-safe in-memory store for users, roles, and API keys."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._roles: dict[str, Role] = {}
        self._api_keys: dict[str, APIKey] = {}
        self._lock = threading.Lock()
        self._init_defaults()

    def _init_defaults(self) -> None:
        from app.config.settings import get_settings
        from app.security.passwords import hash_password

        settings = get_settings()
        admin_pw = settings.default_admin_password

        # Default roles
        for role_name, perms in _DEFAULT_ROLE_PERMISSIONS.items():
            self._roles[role_name.value] = Role(
                name=role_name.value,
                permissions=perms,
                description=f"Built-in {role_name.value} role",
            )

        # Default admin user
        admin_id = "usr_admin"
        self._users[admin_id] = User(
            user_id=admin_id,
            username=settings.default_admin_username,
            hashed_password=hash_password(admin_pw),
            roles=["admin"],
        )

    # ── Users ──────────────────────────────────────────────────

    def get_user(self, user_id: str) -> User | None:
        with self._lock:
            return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> User | None:
        with self._lock:
            for u in self._users.values():
                if u.username == username:
                    return u
        return None

    def list_users(self) -> list[User]:
        with self._lock:
            return list(self._users.values())

    def create_user(self, username: str, hashed_password: str, roles: list[str] | None = None, tenant_id: str = "default") -> User:
        user_id = f"usr_{secrets.token_hex(8)}"
        user = User(
            user_id=user_id,
            username=username,
            hashed_password=hashed_password,
            roles=roles or ["viewer"],
            tenant_id=tenant_id,
        )
        with self._lock:
            self._users[user_id] = user
        return user

    def update_user(self, user_id: str, **kwargs: Any) -> User | None:
        with self._lock:
            user = self._users.get(user_id)
            if user is None:
                return None
            for k, v in kwargs.items():
                if hasattr(user, k):
                    setattr(user, k, v)
            return user

    def delete_user(self, user_id: str) -> bool:
        with self._lock:
            if user_id in self._users:
                del self._users[user_id]
                return True
            return False

    # ── Roles ──────────────────────────────────────────────────

    def get_role(self, name: str) -> Role | None:
        with self._lock:
            return self._roles.get(name)

    def list_roles(self) -> list[Role]:
        with self._lock:
            return list(self._roles.values())

    def create_role(self, name: str, permissions: frozenset[Permission], description: str = "") -> Role:
        role = Role(name=name, permissions=permissions, description=description)
        with self._lock:
            self._roles[name] = role
        return role

    def delete_role(self, name: str) -> bool:
        with self._lock:
            if name in self._roles:
                del self._roles[name]
                return True
            return False

    def get_effective_permissions(self, user: User) -> frozenset[Permission]:
        perms: set[Permission] = set()
        with self._lock:
            for role_name in user.roles:
                role = self._roles.get(role_name)
                if role:
                    perms |= role.permissions
        return frozenset(perms)

    # ── API Keys ───────────────────────────────────────────────

    def create_api_key(self, user_id: str, name: str, scopes: list[str] | None = None) -> tuple[APIKey, str]:
        raw_key = f"ll_{secrets.token_urlsafe(32)}"
        key_hash_val = secrets.token_hex(32)
        key = APIKey(
            key_id=f"key_{secrets.token_hex(8)}",
            key_prefix=raw_key[:12],
            key_hash=key_hash_val,
            user_id=user_id,
            name=name,
            scopes=scopes or [],
        )
        with self._lock:
            self._api_keys[key.key_id] = key
        return key, raw_key

    def get_api_key(self, key_id: str) -> APIKey | None:
        with self._lock:
            return self._api_keys.get(key_id)

    def list_api_keys(self, user_id: str | None = None) -> list[APIKey]:
        with self._lock:
            keys = list(self._api_keys.values())
        if user_id:
            keys = [k for k in keys if k.user_id == user_id]
        return keys

    def delete_api_key(self, key_id: str) -> bool:
        with self._lock:
            if key_id in self._api_keys:
                del self._api_keys[key_id]
                return True
            return False

    def validate_api_key(self, raw_key: str) -> APIKey | None:
        """Validate a raw API key by prefix lookup. Returns the APIKey if valid."""
        prefix = raw_key[:12] if len(raw_key) >= 12 else raw_key
        with self._lock:
            for key in self._api_keys.values():
                if key.key_prefix == prefix and key.is_active:
                    if key.expires_at and time.time() > key.expires_at:
                        return None
                    return key
        return None


# ── Singleton ──────────────────────────────────────────────────────

_store: SecurityStore | None = None
_store_lock = threading.Lock()


def get_security_store() -> SecurityStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = SecurityStore()
    return _store
