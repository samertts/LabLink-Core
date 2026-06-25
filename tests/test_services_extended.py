from __future__ import annotations

import threading
from unittest.mock import patch

from app.core.alerting import AlertManager
from app.core.modes import CommunicationMode
from app.services.health_service import HealthService
from app.services.mode_service import ModeService
from app.services.query_service import QueryService
from app.storage.db import InMemoryDB
from app.storage.result_repository import ResultRepository


class TestHealthService:
    def test_check_ok(self) -> None:
        db = InMemoryDB()
        svc = HealthService(db=db)
        result = svc.check()
        assert result.status == "ok"
        assert result.version == "1.3.0"
        assert result.checks["database"] == "ok"

    def test_check_db_error(self) -> None:
        db = InMemoryDB()
        with patch.object(db, "integrity_check", side_effect=RuntimeError("DB corrupt")):
            svc = HealthService(db=db)
            result = svc.check()
            assert result.checks["database"] == "error"


class TestModeService:
    def test_default_mode(self) -> None:
        svc = ModeService()
        assert svc.get() == CommunicationMode.HYBRID

    def test_set_mode(self) -> None:
        svc = ModeService()
        result = svc.set(CommunicationMode.LOCAL_ONLY)
        assert svc.get() == CommunicationMode.LOCAL_ONLY
        assert result.mode == "local_only"

    def test_get_status(self) -> None:
        svc = ModeService()
        status = svc.get_status()
        assert status.mode == "hybrid"

    def test_thread_safety(self) -> None:
        svc = ModeService()
        errors: list[str] = []

        def writer():
            for i in range(100):
                svc.set(CommunicationMode.CLOUD_ONLY if i % 2 == 0 else CommunicationMode.LOCAL_ONLY)

        def reader():
            for _ in range(100):
                val = svc.get()
                if val not in CommunicationMode:
                    errors.append(f"Invalid mode: {val}")

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []


class TestQueryService:
    def test_list_results_empty(self) -> None:
        repo = ResultRepository()
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert svc.list_results() == []

    def test_list_logs_empty(self) -> None:
        repo = ResultRepository()
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert svc.list_logs() == []

    def test_list_audit_empty(self) -> None:
        repo = ResultRepository()
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert svc.list_audit_trail() == []

    def test_list_offline_empty(self) -> None:
        repo = ResultRepository()
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert svc.list_offline_queue() == []

    def test_list_alerts_empty(self) -> None:
        repo = ResultRepository()
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert svc.list_alerts() == []

    def test_pagination_limit(self) -> None:
        db = InMemoryDB()
        repo = ResultRepository(db)
        for i in range(10):
            db.insert("results", {"i": i})
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        assert len(svc.list_results(limit=3)) == 3

    def test_pagination_offset(self) -> None:
        db = InMemoryDB()
        repo = ResultRepository(db)
        for i in range(10):
            db.insert("results", {"i": i})
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        results = svc.list_results(limit=5, offset=5)
        assert len(results) == 5
        assert results[0]["i"] == 5

    def test_add_audit_event(self) -> None:
        db = InMemoryDB()
        repo = ResultRepository(db)
        alerts = AlertManager()
        svc = QueryService(repository=repo, alerts=alerts)
        svc.add_audit_event(event_type="test_event", payload={"key": "value"})
        audit = svc.list_audit_trail()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "test_event"
