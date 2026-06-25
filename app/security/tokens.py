"""JWT token creation and verification."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from fastapi import HTTPException, status

from app.config.settings import get_settings


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0


def create_access_token(subject: str, roles: list[str], extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = time.time()
    payload = {
        "sub": subject,
        "roles": roles,
        "type": "access",
        "iat": now,
        "exp": now + settings.jwt_access_token_expire_minutes * 60,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    now = time.time()
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": now,
        "exp": now + settings.jwt_refresh_token_expire_days * 86400,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_token_pair(user_id: str, roles: list[str]) -> TokenPair:
    settings = get_settings()
    return TokenPair(
        access_token=create_access_token(user_id, roles),
        refresh_token=create_refresh_token(user_id),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
