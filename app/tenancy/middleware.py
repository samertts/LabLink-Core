"""Tenancy middleware and dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.tokens import decode_token
from app.tenancy.models import TenantContext
from app.tenancy.store import TenantStore, get_tenant_store

_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_tenant_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    request: Request,
    tenant_store: Annotated[TenantStore, Depends(get_tenant_store)],
) -> TenantContext:
    """Extract tenant from JWT token or X-Tenant-ID header."""
    tenant_id: str | None = None

    # Try X-Tenant-ID header first
    header_tenant = request.headers.get("x-tenant-id")
    if header_tenant:
        tenant_id = header_tenant

    # If bearer token present, extract tenant from JWT
    if credentials and not tenant_id:
        try:
            payload = decode_token.__wrapped__(credentials.credentials) if hasattr(decode_token, '__wrapped__') else None
        except Exception:
            payload = None
        if payload:
            tenant_id = payload.get("tenant_id")

    if not tenant_id:
        # Default tenant
        tenant_id = "default"

    tenant = tenant_store.get(tenant_id)
    return TenantContext(tenant_id=tenant_id, tenant=tenant)


TenantContextDep = Annotated[TenantContext, Depends(_extract_tenant_context)]


def require_tenant_active(ctx: TenantContextDep) -> TenantContext:
    """Dependency that rejects requests for inactive tenants."""
    if ctx.tenant is not None and not ctx.tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant '{ctx.tenant_id}' is inactive",
        )
    return ctx
