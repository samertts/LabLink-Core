from __future__ import annotations

from app.storage.db import InMemoryDB
from app.storage.repositories import (
    AuditRepository,
    LogRepositoryProtocol,
    OfflineQueueRepository,
    ResultRepositoryProtocol,
)
from app.storage.result_repository import ResultRepository


class TestRepositoryProtocols:
    def test_result_repository_implements_protocol(self) -> None:
        repo = ResultRepository()
        assert isinstance(repo, ResultRepositoryProtocol)

    def test_log_repository_implements_protocol(self) -> None:
        repo = ResultRepository()
        assert isinstance(repo, LogRepositoryProtocol)

    def test_audit_repository_implements_protocol(self) -> None:
        repo = ResultRepository()
        assert isinstance(repo, AuditRepository)

    def test_offline_queue_implements_protocol(self) -> None:
        repo = ResultRepository()
        assert isinstance(repo, OfflineQueueRepository)

    def test_count_results(self) -> None:
        db = InMemoryDB()
        repo = ResultRepository(db)
        assert repo.count_results() == 0
        db.insert("results", {"a": 1})
        assert repo.count_results() == 1

    def test_list_results_empty(self) -> None:
        repo = ResultRepository()
        assert repo.list_results() == []

    def test_list_logs_empty(self) -> None:
        repo = ResultRepository()
        assert repo.list_logs() == []

    def test_list_audit_trail_empty(self) -> None:
        repo = ResultRepository()
        assert repo.list_audit_trail() == []

    def test_list_offline_queue_empty(self) -> None:
        repo = ResultRepository()
        assert repo.list_offline_queue() == []
