from __future__ import annotations

import threading
from unittest.mock import patch

from app.core.alerting import AlertManager
from app.core.modes import CommunicationMode
from app.storage.db import InMemoryDB


class TestAlertManagerBounded:
    def test_emitting_within_limit(self) -> None:
        mgr = AlertManager(max_alerts=10)
        for i in range(5):
            mgr.emit(severity="info", message=f"msg {i}", device_id="D1")
        assert mgr.count() == 5

    def test_emitting_exceeds_limit_prunes(self) -> None:
        mgr = AlertManager(max_alerts=5)
        for i in range(10):
            mgr.emit(severity="info", message=f"msg {i}", device_id="D1")
        assert mgr.count() == 5
        alerts = mgr.list_alerts()
        assert alerts[0]["message"] == "msg 5"

    def test_clear(self) -> None:
        mgr = AlertManager()
        mgr.emit(severity="info", message="test", device_id="D1")
        mgr.clear()
        assert mgr.count() == 0

    def test_thread_safety(self) -> None:
        mgr = AlertManager(max_alerts=100)

        def emit_many():
            for _ in range(50):
                mgr.emit(severity="info", message="t", device_id="D1")

        threads = [threading.Thread(target=emit_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert mgr.count() == 100


class TestThreadSafeMode:
    def test_get_set(self) -> None:
        from app.services.mode_service import ModeService

        mode = ModeService()
        assert mode.get() == CommunicationMode.HYBRID
        mode.set(CommunicationMode.LOCAL_ONLY)
        assert mode.get() == CommunicationMode.LOCAL_ONLY

    def test_thread_safety(self) -> None:
        from app.services.mode_service import ModeService

        mode = ModeService()
        errors: list[str] = []

        def writer():
            for i in range(100):
                mode.set(CommunicationMode.CLOUD_ONLY if i % 2 == 0 else CommunicationMode.LOCAL_ONLY)

        def reader():
            for _ in range(100):
                val = mode.get()
                if val not in CommunicationMode:
                    errors.append(f"Invalid mode: {val}")

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestInMemoryDB:
    def test_insert_and_select(self) -> None:
        db = InMemoryDB()
        db.insert("results", {"test": "Hb", "value": 13.5})
        rows = db.select_all("results")
        assert len(rows) == 1
        assert rows[0]["test"] == "Hb"

    def test_count(self) -> None:
        db = InMemoryDB()
        assert db.count("results") == 0
        db.insert("results", {"a": 1})
        db.insert("results", {"a": 2})
        assert db.count("results") == 2

    def test_clear(self) -> None:
        db = InMemoryDB()
        db.insert("logs", {"msg": "test"})
        db.clear("logs")
        assert db.count("logs") == 0

    def test_integrity_check(self) -> None:
        db = InMemoryDB()
        assert db.integrity_check() is True

    def test_thread_safety(self) -> None:
        db = InMemoryDB()
        errors: list[str] = []

        def writer():
            for i in range(50):
                db.insert("results", {"i": i})

        def reader():
            for _ in range(50):
                count = db.count("results")
                if count < 0:
                    errors.append(f"Negative count: {count}")

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert db.count("results") == 50

    def test_table_proxy_iteration(self) -> None:
        db = InMemoryDB()
        db.insert("results", {"a": 1})
        db.insert("results", {"a": 2})
        items = list(db.results)
        assert len(items) == 2

    def test_table_proxy_len(self) -> None:
        db = InMemoryDB()
        assert len(db.results) == 0
        db.insert("results", {"a": 1})
        assert len(db.results) == 1

    def test_table_proxy_bool(self) -> None:
        db = InMemoryDB()
        assert not db.results
        db.insert("results", {"a": 1})
        assert db.results

    def test_table_proxy_getitem(self) -> None:
        db = InMemoryDB()
        db.insert("results", {"a": 1})
        db.insert("results", {"a": 2})
        assert db.results[0]["a"] == 1
        assert db.results[1]["a"] == 2


class TestASTMBuilderReset:
    def test_reset_clears_state(self) -> None:
        from app.pipeline.parser_engine import ASTMMessageBuilder, ASTMRecord

        builder = ASTMMessageBuilder()
        builder.process_records([ASTMRecord(type="patient", raw="", patient_id="P1")])
        assert builder.current_patient_id == "P1"
        builder.reset()
        assert builder.current_patient_id is None
        assert builder.current_patient_name is None


class TestInputValidation:
    def test_command_validation_rejects_long_command(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.security.auth import _get_or_generate_api_key

        client = TestClient(app)
        headers = {"x-api-key": _get_or_generate_api_key()}
        long_cmd = "A" * 300
        response = client.post(
            "/devices/DEV-1/command",
            json={"command": long_cmd},
            headers=headers,
        )
        assert response.status_code == 422

    def test_command_validation_rejects_special_chars(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.security.auth import _get_or_generate_api_key

        client = TestClient(app)
        headers = {"x-api-key": _get_or_generate_api_key()}
        response = client.post(
            "/devices/DEV-1/command",
            json={"command": "rm -rf /"},
            headers=headers,
        )
        assert response.status_code == 422


class TestHealthEndpoint:
    def test_health_returns_version_and_checks(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"] == "1.3.0"
        assert "checks" in body


class TestPagination:
    def test_results_pagination(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app
        from app.security.auth import _get_or_generate_api_key

        client = TestClient(app)
        headers = {"x-api-key": _get_or_generate_api_key()}
        response = client.get("/results?limit=5&offset=0", headers=headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestRateLimiter:
    def test_rate_limit_allows_normal_traffic(self) -> None:
        from fastapi.testclient import TestClient
        from app.main import app

        client = TestClient(app)
        for _ in range(5):
            response = client.get("/health")
            assert response.status_code == 200
