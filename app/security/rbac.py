"""RBAC dependency injection for FastAPI endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.models import Permission, User, get_security_store
from app.security.tokens import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def _get_current_user_from_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    """Extract user from Bearer token. Raises 401 if invalid."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub", "")
    store = get_security_store()
    user = store.get_user(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(_get_current_user_from_token)]


def require_permission(permission: Permission):
    """Dependency factory that checks if current user has the given permission."""

    async def _check(user: CurrentUser) -> User:
        store = get_security_store()
        effective = store.get_effective_permissions(user)
        if permission not in effective:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )
        return user

    return _check


def require_role(role_name: str):
    """Dependency factory that checks if current user has the given role."""

    async def _check(user: CurrentUser) -> User:
        if role_name not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required role: {role_name}",
            )
        return user

    return _check


# ── Convenience type aliases for common patterns ───────────────────

RequireDeviceRead = Annotated[User, Depends(require_permission(Permission.DEVICE_READ))]
RequireDeviceWrite = Annotated[User, Depends(require_permission(Permission.DEVICE_WRITE))]
RequireResultRead = Annotated[User, Depends(require_permission(Permission.RESULT_READ))]
RequireResultWrite = Annotated[User, Depends(require_permission(Permission.RESULT_WRITE))]
RequireDriverRead = Annotated[User, Depends(require_permission(Permission.DRIVER_READ))]
RequireDriverInstall = Annotated[User, Depends(require_permission(Permission.DRIVER_INSTALL))]
RequirePluginRead = Annotated[User, Depends(require_permission(Permission.PLUGIN_READ))]
RequirePluginInstall = Annotated[User, Depends(require_permission(Permission.PLUGIN_INSTALL))]
RequireVendorRead = Annotated[User, Depends(require_permission(Permission.VENDOR_READ))]
RequireProtocolRead = Annotated[User, Depends(require_permission(Permission.PROTOCOL_READ))]
RequireDiscoveryRead = Annotated[User, Depends(require_permission(Permission.DISCOVERY_READ))]
RequireDiscoveryScan = Annotated[User, Depends(require_permission(Permission.DISCOVERY_SCAN))]
RequireUserRead = Annotated[User, Depends(require_permission(Permission.USER_READ))]
RequireUserWrite = Annotated[User, Depends(require_permission(Permission.USER_WRITE))]
RequireAuditRead = Annotated[User, Depends(require_permission(Permission.AUDIT_READ))]
RequireSystemAdmin = Annotated[User, Depends(require_permission(Permission.SYSTEM_ADMIN))]
RequireRoleAdmin = Annotated[User, Depends(require_role("admin"))]
