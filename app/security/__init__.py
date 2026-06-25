"""LabLink Security — RBAC, authentication, audit logging."""

from app.security.audit import AuditEvent, AuditEventType, SecurityAuditLog, get_audit_log, log_auth_event
from app.security.middleware import SecurityHeadersMiddleware
from app.security.models import (
    APIKey,
    Permission,
    Role,
    RoleName,
    SecurityStore,
    User,
    get_security_store,
)
from app.security.passwords import hash_password, verify_password
from app.security.rbac import (
    CurrentUser,
    require_permission,
    require_role,
)
from app.security.tokens import TokenPair, create_access_token, create_refresh_token, create_token_pair, decode_token

__all__ = [
    "APIKey",
    "AuditEvent",
    "AuditEventType",
    "CurrentUser",
    "Permission",
    "Role",
    "RoleName",
    "SecurityAuditLog",
    "SecurityHeadersMiddleware",
    "SecurityStore",
    "TokenPair",
    "User",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "get_audit_log",
    "get_security_store",
    "hash_password",
    "log_auth_event",
    "require_permission",
    "require_role",
    "verify_password",
]
