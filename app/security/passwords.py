"""Password hashing and verification utilities."""

from __future__ import annotations

from passlib.hash import bcrypt, bcrypt_sha256


def hash_password(plain: str) -> str:
    """Hash with bcrypt-sha256 so bcrypt's 72-byte input limit is never reached."""
    return bcrypt_sha256.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify current bcrypt-sha256 hashes and legacy bcrypt hashes."""
    if hashed.startswith("$bcrypt-sha256$"):
        return bcrypt_sha256.verify(plain, hashed)
    return bcrypt.verify(plain, hashed)
