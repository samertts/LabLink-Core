"""Backup engine — create, restore, list, verify, and delete backups."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from app.backup.models import BackupManifest, BackupStatus, BackupType, RestoreResult, RetentionPolicy
from app.settings.paths import BACKUPS_DIR

logger = logging.getLogger("lablink.backup")

TABLES = ["results", "logs", "audit_trail", "offline_queue"]


class BackupEngine:
    """Thread-safe backup engine for the SQLite database."""

    def __init__(
        self,
        db_path: str,
        backups_dir: Path | None = None,
        retention: RetentionPolicy | None = None,
    ) -> None:
        self._db_path = db_path
        self._backups_dir = backups_dir or BACKUPS_DIR
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        self._retention = retention or RetentionPolicy()
        self._lock = threading.Lock()
        self._manifests: list[BackupManifest] = []
        self._load_manifests()

    # ── Backup ─────────────────────────────────────────────────

    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        tables: list[str] | None = None,
        compression: str = "none",
    ) -> BackupManifest:
        tables = tables or TABLES
        manifest = BackupManifest(
            backup_type=backup_type,
            tables_included=tables,
            compression=compression,
        )
        manifest.status = BackupStatus.IN_PROGRESS

        start = time.monotonic()
        try:
            backup_file = self._backup_file_path(manifest)
            manifest.file_path = str(backup_file)

            if compression == "gzip":
                self._backup_sqlite_to_gzip(backup_file, tables)
            else:
                self._backup_sqlite_to_json(backup_file, tables)

            manifest.file_size_bytes = backup_file.stat().st_size
            manifest.checksum_sha256 = self._checksum(backup_file)
            manifest.row_counts = self._count_rows(tables)
            manifest.duration_seconds = time.monotonic() - start
            manifest.completed_at = time.time()
            manifest.status = BackupStatus.COMPLETED

            logger.info("Backup completed: %s (%d bytes)", manifest.backup_id, manifest.file_size_bytes)
        except Exception as exc:
            manifest.status = BackupStatus.FAILED
            manifest.error = str(exc)
            manifest.duration_seconds = time.monotonic() - start
            logger.error("Backup failed: %s — %s", manifest.backup_id, exc)

        with self._lock:
            self._manifests.append(manifest)
            self._save_manifests()

        return manifest

    def _backup_sqlite_to_json(self, dest: Path, tables: list[str]) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            data: dict[str, list[dict[str, Any]]] = {}
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT data FROM {table} ORDER BY id")
                    rows = [json.loads(row[0]) for row in cursor.fetchall()]
                    data[table] = rows
                except sqlite3.OperationalError:
                    data[table] = []
            with open(dest, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "tables": data, "created_at": time.time()}, f, default=str)
        finally:
            conn.close()

    def _backup_sqlite_to_gzip(self, dest: Path, tables: list[str]) -> None:
        import gzip
        conn = sqlite3.connect(self._db_path)
        try:
            data: dict[str, list[dict[str, Any]]] = {}
            for table in tables:
                try:
                    cursor = conn.execute(f"SELECT data FROM {table} ORDER BY id")
                    rows = [json.loads(row[0]) for row in cursor.fetchall()]
                    data[table] = rows
                except sqlite3.OperationalError:
                    data[table] = []
            payload = json.dumps({"version": 1, "tables": data, "created_at": time.time()}, default=str).encode()
            with gzip.open(dest, "wb", compresslevel=6) as f:
                f.write(payload)
        finally:
            conn.close()

    # ── Restore ────────────────────────────────────────────────

    def restore_backup(self, backup_id: str) -> RestoreResult:
        manifest = self.get_manifest(backup_id)
        if manifest is None:
            return RestoreResult(success=False, error=f"Backup '{backup_id}' not found")

        if manifest.status != BackupStatus.COMPLETED:
            return RestoreResult(success=False, error=f"Backup '{backup_id}' is not completed (status={manifest.status.value})")

        backup_file = Path(manifest.file_path)
        if not backup_file.exists():
            return RestoreResult(success=False, error=f"Backup file not found: {manifest.file_path}")

        start = time.monotonic()
        try:
            data = self._load_backup_file(backup_file)
            tables_data = data.get("tables", {})

            conn = sqlite3.connect(self._db_path)
            try:
                rows_restored = 0
                tables_restored = []
                for table, rows in tables_data.items():
                    if not rows:
                        continue
                    conn.execute(f"DELETE FROM {table}")
                    for row in rows:
                        conn.execute(
                            f"INSERT INTO {table} (data, created_at) VALUES (?, ?)",
                            (json.dumps(row), row.get("created_at", time.time())),
                        )
                        rows_restored += 1
                    tables_restored.append(table)
                conn.commit()
            finally:
                conn.close()

            duration = time.monotonic() - start
            logger.info("Restore completed: %s (%d rows)", backup_id, rows_restored)
            return RestoreResult(
                success=True,
                tables_restored=tables_restored,
                rows_restored=rows_restored,
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.monotonic() - start
            logger.error("Restore failed: %s — %s", backup_id, exc)
            return RestoreResult(success=False, duration_seconds=duration, error=str(exc))

    def _load_backup_file(self, path: Path) -> dict[str, Any]:
        if path.suffix == ".gz":
            import gzip
            with gzip.open(path, "rb") as f:
                return json.loads(f.read())
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ── Verify ─────────────────────────────────────────────────

    def verify_backup(self, backup_id: str) -> bool:
        manifest = self.get_manifest(backup_id)
        if manifest is None:
            return False
        backup_file = Path(manifest.file_path)
        if not backup_file.exists():
            manifest.status = BackupStatus.FAILED
            manifest.error = "File missing"
            return False
        actual_checksum = self._checksum(backup_file)
        if actual_checksum != manifest.checksum_sha256:
            manifest.status = BackupStatus.FAILED
            manifest.error = f"Checksum mismatch: expected {manifest.checksum_sha256}, got {actual_checksum}"
            self._save_manifests()
            return False
        manifest.status = BackupStatus.VERIFIED
        self._save_manifests()
        return True

    # ── List / Delete ──────────────────────────────────────────

    def list_backups(self) -> list[dict[str, Any]]:
        with self._lock:
            return [m.to_dict() for m in self._manifests]

    def get_manifest(self, backup_id: str) -> BackupManifest | None:
        with self._lock:
            for m in self._manifests:
                if m.backup_id == backup_id:
                    return m
        return None

    def delete_backup(self, backup_id: str) -> bool:
        with self._lock:
            for i, m in enumerate(self._manifests):
                if m.backup_id == backup_id:
                    backup_file = Path(m.file_path)
                    if backup_file.exists():
                        backup_file.unlink()
                    self._manifests.pop(i)
                    self._save_manifests()
                    logger.info("Deleted backup: %s", backup_id)
                    return True
        return False

    def enforce_retention(self) -> list[str]:
        """Delete backups that exceed retention policy. Returns deleted IDs."""
        deleted: list[str] = []
        with self._lock:
            count = len(self._manifests)
            for m in list(self._manifests):
                if self._retention.should_delete(m, count):
                    backup_file = Path(m.file_path)
                    if backup_file.exists():
                        backup_file.unlink()
                    self._manifests.remove(m)
                    count -= 1
                    deleted.append(m.backup_id)
                    logger.info("Retention: deleted backup %s", m.backup_id)
            if deleted:
                self._save_manifests()
        return deleted

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._manifests)
            completed = sum(1 for m in self._manifests if m.status == BackupStatus.COMPLETED)
            total_size = sum(m.file_size_bytes for m in self._manifests)
            return {
                "total_backups": total,
                "completed": completed,
                "total_size_bytes": total_size,
                "retention": {
                    "max_backups": self._retention.max_backups,
                    "max_age_days": self._retention.max_age_days,
                },
            }

    # ── Internal ───────────────────────────────────────────────

    def _backup_file_path(self, manifest: BackupManifest) -> Path:
        ext = ".json.gz" if manifest.compression == "gzip" else ".json"
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime(manifest.created_at))
        return self._backups_dir / f"{manifest.backup_id}_{ts}{ext}"

    def _checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _count_rows(self, tables: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        try:
            conn = sqlite3.connect(self._db_path)
            for table in tables:
                try:
                    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
                    counts[table] = row[0] if row else 0
                except sqlite3.OperationalError:
                    counts[table] = 0
            conn.close()
        except Exception:
            pass
        return counts

    def _manifests_path(self) -> Path:
        return self._backups_dir / "manifests.json"

    def _load_manifests(self) -> None:
        path = self._manifests_path()
        if not path.exists():
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._manifests = [
                BackupManifest(
                    backup_id=m["backup_id"],
                    backup_type=BackupType(m["backup_type"]),
                    status=BackupStatus(m["status"]),
                    created_at=m["created_at"],
                    completed_at=m.get("completed_at"),
                    file_path=m.get("file_path", ""),
                    file_size_bytes=m.get("file_size_bytes", 0),
                    checksum_sha256=m.get("checksum_sha256", ""),
                    tables_included=m.get("tables_included", []),
                    row_counts=m.get("row_counts", {}),
                    compression=m.get("compression", "none"),
                    duration_seconds=m.get("duration_seconds", 0),
                    error=m.get("error"),
                    metadata=m.get("metadata", {}),
                )
                for m in data
            ]
        except Exception:
            self._manifests = []

    def _save_manifests(self) -> None:
        path = self._manifests_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump([m.to_dict() for m in self._manifests], f, indent=2, default=str)
