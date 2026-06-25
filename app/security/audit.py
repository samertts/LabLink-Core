"""Security audit logging — tracks auth events, permission denials, and admin actions."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuditEventType(str, Enum):
    LOGIN_SUCCESS = "login.success"
    LOGIN_FAILURE = "login.failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token.refresh"
    TOKEN_REVOKED = "token.revoked"
    PASSWORD_CHANGED = "password.changed"
    USER_CREATED = "user.created"
    USER_DELETED = "user.deleted"
    USER_LOCKED = "user.locked"
    USER_UNLOCKED = "user.unlocked"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_REVOKED = "role.revoked"
    PERMISSION_DENIED = "permission.denied"
    APIKEY_CREATED = "apikey.created"
    APIKEY_REVOKED = "apikey.revoked"
    APIKEY_USED = "apikey.used"
    ADMIN_ACTION = "admin.action"


@dataclass
class AuditEvent:
    event_type: AuditEventType
    actor_id: str
    target_id: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "detail": self.detail,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "timestamp": self.timestamp,
            "success": self.success,
        }


class SecurityAuditLog:
    """Thread-safe in-memory audit log with configurable max size."""

    def __init__(self, max_events: int = 10_000) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()
        self._max_events = max_events

    def log(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

    def query(
        self,
        event_type: AuditEventType | None = None,
        actor_id: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        with self._lock:
            events = list(self._events)

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if actor_id:
            events = [e for e in events if e.actor_id == actor_id]
        if since:
            events = [e for e in events if e.timestamp >= since]

        return events[-limit:]

    def count(self, event_type: AuditEventType | None = None) -> int:
        with self._lock:
            if event_type:
                return sum(1 for e in self._events if e.event_type == event_type)
            return len(self._events)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_audit_log: SecurityAuditLog | None = None
_audit_lock = threading.Lock()


def get_audit_log() -> SecurityAuditLog:
    global _audit_log
    if _audit_log is None:
        with _audit_lock:
            if _audit_log is None:
                _audit_log = SecurityAuditLog()
    return _audit_log


def log_auth_event(
    event_type: AuditEventType,
    actor_id: str,
    *,
    target_id: str = "",
    detail: dict[str, Any] | None = None,
    ip_address: str = "",
    user_agent: str = "",
    success: bool = True,
) -> None:
    """Convenience wrapper to log an audit event."""
    get_audit_log().log(AuditEvent(
        event_type=event_type,
        actor_id=actor_id,
        target_id=target_id,
        detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    ))
