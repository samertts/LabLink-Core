from __future__ import annotations

import logging
import os
import secrets

from fastapi import Header, HTTPException

logger = logging.getLogger("lablink.security")

API_KEY_ENV = "LABLINK_API_KEY"

_generated_key: str | None = None


def _get_or_generate_api_key() -> str:
    global _generated_key
    env_key = os.getenv(API_KEY_ENV)
    if env_key:
        return env_key
    if _generated_key is None:
        _generated_key = secrets.token_urlsafe(32)
        logger.warning(
            "No LABLINK_API_KEY environment variable set. Generated a random API key for this session. "
            "Set LABLINK_API_KEY in your environment for production use."
        )
    return _generated_key


DEFAULT_API_KEY: str = ""


def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    expected = _get_or_generate_api_key()
    if not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key or ""
