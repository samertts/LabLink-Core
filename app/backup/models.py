"""Backup & Recovery — models and configuration."""

from __future__ import annotations

import enum
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


class BackupType(str, enum.Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    SNAPSHOT = "snapshot"


class BackupStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFYING = "verifying"
    VERIFIED = "verified"


@dataclass
class BackupManifest:
    """Metadata for a single backup."""
    backup_id: str = field(default_factory=lambda: f"bkp_{secrets.token_hex(8)}")
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    file_path: str = ""
    file_size_bytes: int = 0
    checksum_sha256: str = ""
    tables_included: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    compression: str = "none"
    duration_seconds: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "backup_type": self.backup_type.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "tables_included": self.tables_included,
            "row_counts": self.row_counts,
            "compression": self.compression,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class RetentionPolicy:
    """Controls how many backups to keep and how long to retain them."""
    max_backups: int = 10
    max_age_days: int = 30
    min_keep: int = 2  # always keep at least this many

    def should_delete(self, manifest: BackupManifest, total_count: int) -> bool:
        if total_count <= self.min_keep:
            return False
        age_days = (time.time() - manifest.created_at) / 86400
        return age_days > self.max_age_days


@dataclass
class RestoreResult:
    success: bool
    tables_restored: list[str] = field(default_factory=list)
    rows_restored: int = 0
    duration_seconds: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "tables_restored": self.tables_restored,
            "rows_restored": self.rows_restored,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
        }
