from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from app.settings.paths import DATA_DIR


class InMemoryDB:
    """SQLite-backed persistent storage with in-memory list interface.

    Falls back to pure in-memory lists if SQLite is unavailable.
    Thread-safe via a lock.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._use_sqlite = False
        self._fallback: dict[str, list[dict[str, Any]]] = {
            "results": [],
            "logs": [],
            "audit_trail": [],
            "offline_queue": [],
        }

        if db_path is None:
            db_path = ":memory:"

        try:
            if db_path != ":memory:":
                DATA_DIR.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._init_tables()
            self._use_sqlite = True
        except Exception:
            self._conn = None
            self._use_sqlite = False

        self.results: list[dict[str, Any]] = _TableProxy(self, "results")  # type: ignore[assignment]
        self.logs: list[dict[str, Any]] = _TableProxy(self, "logs")  # type: ignore[assignment]
        self.audit_trail: list[dict[str, Any]] = _TableProxy(self, "audit_trail")  # type: ignore[assignment]
        self.offline_queue: list[dict[str, Any]] = _TableProxy(self, "offline_queue")  # type: ignore[assignment]

    def _init_tables(self) -> None:
        if self._conn is None:
            return
        for table in ("results", "logs", "audit_trail", "offline_queue"):
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table} "
                "(id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
        self._conn.commit()

    def insert(self, table: str, row: dict[str, Any]) -> None:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                self._conn.execute(
                    f"INSERT INTO {table} (data, created_at) VALUES (?, ?)",
                    (json.dumps(row, default=str), datetime.now(timezone.utc).isoformat()),
                )
                self._conn.commit()
            else:
                self._fallback[table].append(row)

    def select_all(self, table: str) -> list[dict[str, Any]]:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                cursor = self._conn.execute(f"SELECT data FROM {table} ORDER BY id")
                return [json.loads(row[0]) for row in cursor.fetchall()]
            return list(self._fallback[table])

    def count(self, table: str) -> int:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                cursor = self._conn.execute(f"SELECT COUNT(*) FROM {table}")
                return cursor.fetchone()[0]
            return len(self._fallback[table])

    def clear(self, table: str) -> None:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                self._conn.execute(f"DELETE FROM {table}")
                self._conn.commit()
            else:
                self._fallback[table].clear()

    def truncate(self, table: str, keep_last: int = 1000) -> None:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                self._conn.execute(
                    f"DELETE FROM {table} WHERE id NOT IN "
                    f"(SELECT id FROM {table} ORDER BY id DESC LIMIT ?)",
                    (keep_last,),
                )
                self._conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def integrity_check(self) -> bool:
        with self._lock:
            if self._use_sqlite and self._conn is not None:
                try:
                    result = self._conn.execute("PRAGMA integrity_check").fetchone()
                    return result is not None and result[0] == "ok"
                except Exception:
                    return False
            return True


class _TableProxy:
    """List-like proxy that delegates to InMemoryDB for thread-safe storage."""

    def __init__(self, db: InMemoryDB, table: str) -> None:
        object.__setattr__(self, "_db", db)
        object.__setattr__(self, "_table", table)

    def _get_db(self) -> InMemoryDB:
        return object.__getattribute__(self, "_db")

    def _get_table(self) -> str:
        return object.__getattribute__(self, "_table")

    def append(self, item: dict[str, Any]) -> None:
        self._get_db().insert(self._get_table(), item)

    def extend(self, items: list[dict[str, Any]]) -> None:
        for item in items:
            self.append(item)

    def __len__(self) -> int:
        return self._get_db().count(self._get_table())

    def __iter__(self):
        return iter(self._get_db().select_all(self._get_table()))

    def __getitem__(self, index):
        return self._get_db().select_all(self._get_table())[index]

    def __bool__(self) -> bool:
        return self._get_db().count(self._get_table()) > 0

    def clear(self) -> None:
        self._get_db().clear(self._get_table())

    def list(self) -> list[dict[str, Any]]:
        return self._get_db().select_all(self._get_table())
