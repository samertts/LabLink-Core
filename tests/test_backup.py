"""Tests for Backup & Recovery — engine, restore, retention, verify (Phase 8)."""

from __future__ import annotations

import time
from pathlib import Path

from app.backup.engine import BackupEngine
from app.backup.models import BackupManifest, BackupStatus, RestoreResult, RetentionPolicy
from app.storage.db import InMemoryDB

# ── Helpers ────────────────────────────────────────────────────────


def _make_db(path: str) -> InMemoryDB:
    db = InMemoryDB(db_path=path)
    db.insert("results", {"patient_id": "P1", "test": "HGB", "value": 14.2})
    db.insert("results", {"patient_id": "P2", "test": "WBC", "value": 7.5})
    db.insert("logs", {"device_id": "D1", "raw": "data"})
    db.insert("audit_trail", {"event_type": "result_saved", "payload": {}})
    return db


# ── BackupEngine Tests ────────────────────────────────────────────


class TestBackupEngine:
    def test_create_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()
        assert manifest.status == BackupStatus.COMPLETED
        assert manifest.file_size_bytes > 0
        assert manifest.checksum_sha256 != ""
        assert manifest.row_counts.get("results", 0) == 2
        db.close()

    def test_create_gzip_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup(compression="gzip")
        assert manifest.status == BackupStatus.COMPLETED
        assert manifest.file_path.endswith(".json.gz")
        db.close()

    def test_list_backups(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        engine.create_backup()
        backups = engine.list_backups()
        assert len(backups) == 1
        assert backups[0]["status"] == "completed"
        db.close()

    def test_get_manifest(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()
        found = engine.get_manifest(manifest.backup_id)
        assert found is not None
        assert found.backup_id == manifest.backup_id
        assert engine.get_manifest("nonexistent") is None
        db.close()

    def test_verify_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()
        assert engine.verify_backup(manifest.backup_id) is True
        verified = engine.get_manifest(manifest.backup_id)
        assert verified is not None
        assert verified.status == BackupStatus.VERIFIED
        db.close()

    def test_verify_tampered_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()
        # Tamper with file
        with open(manifest.file_path, "w") as f:
            f.write("tampered")
        assert engine.verify_backup(manifest.backup_id) is False
        db.close()

    def test_delete_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()
        assert engine.delete_backup(manifest.backup_id) is True
        assert engine.get_manifest(manifest.backup_id) is None
        assert engine.delete_backup("nonexistent") is False
        db.close()

    def test_summary(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        engine.create_backup()
        s = engine.summary()
        assert s["total_backups"] == 1
        assert s["completed"] == 1
        assert s["total_size_bytes"] > 0
        db.close()


# ── Restore Tests ─────────────────────────────────────────────────


class TestRestore:
    def test_restore_backup(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup()

        # Clear and verify empty
        db.clear("results")
        assert db.count("results") == 0

        # Restore
        result = engine.restore_backup(manifest.backup_id)
        assert result.success is True
        assert result.rows_restored > 0
        assert db.count("results") == 2
        db.close()

    def test_restore_nonexistent(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        result = engine.restore_backup("nonexistent")
        assert result.success is False
        assert "not found" in result.error

    def test_restore_gzip(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups")
        manifest = engine.create_backup(compression="gzip")

        db.clear("results")
        result = engine.restore_backup(manifest.backup_id)
        assert result.success is True
        assert db.count("results") == 2
        db.close()


# ── Retention Tests ───────────────────────────────────────────────


class TestRetention:
    def test_enforce_retention(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        policy = RetentionPolicy(max_backups=3, max_age_days=30, min_keep=1)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups", retention=policy)

        # Create 5 backups and backdate them so retention can clean them
        manifests = []
        for _ in range(5):
            m = engine.create_backup()
            m.created_at = time.time() - 86400 * 40  # 40 days old
            manifests.append(m)
        # Persist backdated timestamps
        engine._save_manifests()

        deleted = engine.enforce_retention()
        assert len(deleted) > 0
        remaining = engine.list_backups()
        assert len(remaining) <= 3
        db.close()

    def test_retention_preserves_minimum(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "test.db")
        db = _make_db(db_path)
        policy = RetentionPolicy(max_backups=1, max_age_days=0, min_keep=2)
        engine = BackupEngine(db_path=db_path, backups_dir=tmp_path / "backups", retention=policy)

        for _ in range(3):
            m = engine.create_backup()
            # Backdate to force expiry
            m.created_at = time.time() - 86400 * 60

        engine.enforce_retention()
        remaining = engine.list_backups()
        assert len(remaining) >= 2  # min_keep=2
        db.close()

    def test_retention_model_should_delete(self) -> None:
        policy = RetentionPolicy(max_backups=5, max_age_days=30, min_keep=2)
        # Under min_keep — never delete
        m = BackupManifest(created_at=time.time() - 86400 * 60)
        assert policy.should_delete(m, total_count=1) is False
        # Over max_age_days
        m_old = BackupManifest(created_at=time.time() - 86400 * 40)
        assert policy.should_delete(m_old, total_count=10) is True


# ── Model Tests ───────────────────────────────────────────────────


class TestModels:
    def test_backup_manifest_to_dict(self) -> None:
        m = BackupManifest(backup_id="b1", status=BackupStatus.COMPLETED)
        d = m.to_dict()
        assert d["backup_id"] == "b1"
        assert d["status"] == "completed"

    def test_restore_result_to_dict(self) -> None:
        r = RestoreResult(success=True, rows_restored=10)
        d = r.to_dict()
        assert d["success"] is True
        assert d["rows_restored"] == 10
