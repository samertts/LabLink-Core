"""Password hashing and verification utilities."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(plain: str) -> str:
    """Return a bcrypt-sha256 hash while preserving legacy bcrypt verification."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Check plaintext against bcrypt hash."""
    return _pwd_context.verify(plain, hashed)
