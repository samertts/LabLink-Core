from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryDB:
    results: list[dict[str, Any]] = field(default_factory=list)
    logs: list[dict[str, Any]] = field(default_factory=list)
    audit_trail: list[dict[str, Any]] = field(default_factory=list)
    offline_queue: list[dict[str, Any]] = field(default_factory=list)
