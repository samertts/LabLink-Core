"""Unit tests for Enterprise Security — RBAC, tokens, audit (Phase 6)."""

from __future__ import annotations

import pytest

from app.security.audit import AuditEvent, AuditEventType, SecurityAuditLog, get_audit_log, log_auth_event
from app.security.models import (
    Permission,
    RoleName,
    SecurityStore,
)
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, create_refresh_token, create_token_pair, decode_token

# ── Password Tests ─────────────────────────────────────────────────


class TestPasswords:
    def test_hash_and_verify(self) -> None:
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_different_hashes(self) -> None:
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2  # bcrypt salts differ


# ── Token Tests ────────────────────────────────────────────────────


class TestTokens:
    def test_create_and_decode_access_token(self) -> None:
        token = create_access_token("user1", ["admin"])
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["roles"] == ["admin"]
        assert payload["type"] == "access"

    def test_create_refresh_token(self) -> None:
        token = create_refresh_token("user1")
        payload = decode_token(token)
        assert payload["sub"] == "user1"
        assert payload["type"] == "refresh"

    def test_token_pair(self) -> None:
        pair = create_token_pair("user1", ["viewer"])
        assert pair.token_type == "bearer"
        assert pair.expires_in > 0
        access = decode_token(pair.access_token)
        refresh = decode_token(pair.refresh_token)
        assert access["type"] == "access"
        assert refresh["type"] == "refresh"

    def test_invalid_token(self) -> None:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            decode_token("not.a.valid.token")
        assert exc_info.value.status_code == 401


# ── SecurityStore Tests ────────────────────────────────────────────


class TestSecurityStore:
    def test_default_admin_user(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        assert admin.roles == ["admin"]
        assert verify_password("admin", admin.hashed_password)

    def test_create_user(self) -> None:
        store = SecurityStore()
        user = store.create_user("testuser", hash_password("pass123"), roles=["viewer"])
        assert user.username == "testuser"
        assert user.roles == ["viewer"]
        assert store.get_user(user.user_id) is not None

    def test_get_user_by_username(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        assert store.get_user_by_username("nonexistent") is None

    def test_update_user(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        store.update_user(admin.user_id, is_active=False)
        updated = store.get_user(admin.user_id)
        assert updated is not None
        assert updated.is_active is False

    def test_delete_user(self) -> None:
        store = SecurityStore()
        user = store.create_user("delme", hash_password("pass"))
        assert store.delete_user(user.user_id) is True
        assert store.get_user(user.user_id) is None
        assert store.delete_user("nonexistent") is False

    def test_create_role(self) -> None:
        store = SecurityStore()
        role = store.create_role("custom", frozenset({Permission.DEVICE_READ}), description="Custom")
        assert role.name == "custom"
        assert Permission.DEVICE_READ in role.permissions

    def test_delete_role(self) -> None:
        store = SecurityStore()
        store.create_role("temp", frozenset())
        assert store.delete_role("temp") is True
        assert store.delete_role("temp") is False

    def test_get_effective_permissions_admin(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        perms = store.get_effective_permissions(admin)
        assert Permission.SYSTEM_ADMIN in perms
        assert Permission.DEVICE_READ in perms

    def test_get_effective_permissions_viewer(self) -> None:
        store = SecurityStore()
        user = store.create_user("viewer1", hash_password("pass"), roles=["viewer"])
        perms = store.get_effective_permissions(user)
        assert Permission.DEVICE_READ in perms
        assert Permission.DEVICE_WRITE not in perms

    def test_list_users(self) -> None:
        store = SecurityStore()
        users = store.list_users()
        assert len(users) >= 1  # at least admin

    def test_list_roles(self) -> None:
        store = SecurityStore()
        roles = store.list_roles()
        assert len(roles) >= 3  # viewer, operator, admin


# ── API Key Tests ──────────────────────────────────────────────────


class TestAPIKeys:
    def test_create_and_validate(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        key, raw = store.create_api_key(admin.user_id, "test-key")
        assert raw.startswith("ll_")
        assert key.key_prefix == raw[:12]
        validated = store.validate_api_key(raw)
        assert validated is not None
        assert validated.key_id == key.key_id

    def test_list_and_delete(self) -> None:
        store = SecurityStore()
        admin = store.get_user_by_username("admin")
        assert admin is not None
        key, _ = store.create_api_key(admin.user_id, "mykey")
        keys = store.list_api_keys(admin.user_id)
        assert len(keys) >= 1
        assert store.delete_api_key(key.key_id) is True
        assert store.delete_api_key(key.key_id) is False


# ── RBAC Tests ─────────────────────────────────────────────────────


class TestRBAC:
    def test_permission_enum(self) -> None:
        assert Permission.DEVICE_READ.value == "device:read"
        assert len(Permission) == 29

    def test_role_name_enum(self) -> None:
        assert RoleName.ADMIN.value == "admin"
        assert RoleName.VIEWER.value == "viewer"
        assert RoleName.OPERATOR.value == "operator"

    def test_viewer_permissions_subset_of_operator(self) -> None:
        from app.security.models import OPERATOR_PERMISSIONS, VIEWER_PERMISSIONS
        assert VIEWER_PERMISSIONS < OPERATOR_PERMISSIONS

    def test_operator_permissions_subset_of_admin(self) -> None:
        from app.security.models import ADMIN_PERMISSIONS, OPERATOR_PERMISSIONS
        assert OPERATOR_PERMISSIONS < ADMIN_PERMISSIONS


# ── Audit Log Tests ────────────────────────────────────────────────


class TestAuditLog:
    def test_log_and_query(self) -> None:
        log = SecurityAuditLog()
        log.log(AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS, actor_id="u1"))
        log.log(AuditEvent(event_type=AuditEventType.LOGIN_FAILURE, actor_id="u2"))
        events = log.query(actor_id="u1")
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.LOGIN_SUCCESS

    def test_count(self) -> None:
        log = SecurityAuditLog()
        log.log(AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS, actor_id="u1"))
        log.log(AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS, actor_id="u2"))
        assert log.count(AuditEventType.LOGIN_SUCCESS) == 2
        assert log.count() == 2

    def test_max_events_rotation(self) -> None:
        log = SecurityAuditLog(max_events=3)
        for i in range(5):
            log.log(AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS, actor_id=f"u{i}"))
        assert log.count() == 3

    def test_clear(self) -> None:
        log = SecurityAuditLog()
        log.log(AuditEvent(event_type=AuditEventType.LOGIN_SUCCESS, actor_id="u1"))
        log.clear()
        assert log.count() == 0

    def test_log_auth_event_convenience(self) -> None:
        log = get_audit_log()
        before = log.count()
        log_auth_event(AuditEventType.LOGIN_SUCCESS, "test_user", ip_address="127.0.0.1")
        assert log.count() == before + 1


# ── AuditEvent.to_dict Tests ───────────────────────────────────────


class TestAuditEvent:
    def test_to_dict(self) -> None:
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_SUCCESS,
            actor_id="u1",
            target_id="u2",
            detail={"key": "val"},
            ip_address="127.0.0.1",
            user_agent="test",
            success=True,
        )
        d = event.to_dict()
        assert d["event_type"] == "login.success"
        assert d["actor_id"] == "u1"
        assert d["success"] is True
        assert d["detail"]["key"] == "val"
