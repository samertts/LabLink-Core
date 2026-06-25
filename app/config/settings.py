from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Centralized, typed configuration for LabLink Core.

    Resolution order:
    1. Environment variables (prefixed with ``LABLINK_``)
    2. ``config.json`` / ``config.yaml`` file (if present)
    3. Defaults defined here
    """

    model_config = {"env_prefix": "LABLINK_", "env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    app_name: str = "LabLink Core"
    version: str = "1.3.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    host: str = "0.0.0.0"
    port: int = 8000

    api_key: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["http://127.0.0.1:8000", "http://localhost:8000"])
    rate_limit_max_requests: int = 200
    rate_limit_window_seconds: int = 60

    gula_url: str = "http://gula.local"
    gula_lab_id: str = "LAB001"

    db_path: str = ""
    data_dir: Path = Field(default_factory=lambda: Path("storage/data"))

    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"

    worker_enabled: bool = True
    worker_poll_interval_seconds: float = 1.0
    worker_max_retries: int = 3

    health_check_interval_seconds: float = 30.0

    @field_validator("data_dir", mode="before")
    @classmethod
    def _ensure_data_dir(cls, v: str | Path) -> Path:
        p = Path(v) if isinstance(v, str) else v
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def effective_db_path(self) -> str:
        if self.db_path:
            return self.db_path
        return str(self.data_dir / "lablink.db")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
