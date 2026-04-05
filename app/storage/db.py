from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DBConfig:
    dsn: str


class DB:
    """Phase-1 placeholder. Real Postgres wiring lands in next phase."""

    def __init__(self, config: DBConfig | None = None) -> None:
        self.config = config

    def health(self) -> str:
        return "ok"
