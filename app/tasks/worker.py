from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("lablink.tasks")


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    status: TaskStatus
    data: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class Task:
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    retries: int = 0
    max_retries: int = 3


TaskHandler = Callable[[Task], TaskResult]


class BackgroundWorker:
    """Lightweight background worker that processes tasks from a queue.

    Thread-safe.  Supports periodic maintenance tasks and one-shot tasks.
    """

    def __init__(self, poll_interval: float = 1.0, max_retries: int = 3) -> None:
        self._lock = threading.Lock()
        self._queue: list[Task] = []
        self._handlers: dict[str, TaskHandler] = {}
        self._periodic: list[tuple[str, TaskHandler, float]] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._poll_interval = poll_interval
        self._max_retries = max_retries
        self._task_results: list[dict[str, Any]] = []
        self._max_results = 500

    def register_handler(self, task_name: str, handler: TaskHandler) -> None:
        with self._lock:
            self._handlers[task_name] = handler

    def register_periodic(self, task_name: str, handler: TaskHandler, interval_seconds: float) -> None:
        with self._lock:
            self._periodic.append((task_name, handler, interval_seconds))

    def enqueue(self, task: Task) -> str:
        with self._lock:
            task.max_retries = self._max_retries
            self._queue.append(task)
        logger.debug("Task enqueued: %s (%s)", task.name, task.task_id)
        return task.task_id

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="lablink-worker")
        self._thread.start()
        logger.info("Background worker started")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("Background worker stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def get_results(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._task_results[-limit:])

    def _run_loop(self) -> None:
        last_periodic: dict[str, float] = {}
        while self._running:
            self._process_queue()
            now = time.monotonic()
            for task_name, handler, interval in self._periodic:
                last_run = last_periodic.get(task_name, 0.0)
                if now - last_run >= interval:
                    last_periodic[task_name] = now
                    self._run_periodic(task_name, handler)
            time.sleep(self._poll_interval)

    def _process_queue(self) -> None:
        while True:
            with self._lock:
                if not self._queue:
                    break
                task = self._queue.pop(0)

            handler = self._handlers.get(task.name)
            if handler is None:
                logger.warning("No handler for task: %s", task.name)
                self._record_result(task, TaskResult(status=TaskStatus.FAILED, error="No handler registered"))
                continue

            task.status = TaskStatus.RUNNING
            start = time.monotonic()
            try:
                result = handler(task)
                result.duration_ms = (time.monotonic() - start) * 1000
                task.status = TaskStatus.COMPLETED
                self._record_result(task, result)
            except Exception as exc:
                task.retries += 1
                if task.retries <= task.max_retries:
                    task.status = TaskStatus.PENDING
                    with self._lock:
                        self._queue.append(task)
                    logger.warning("Task %s failed (retry %d/%d): %s", task.name, task.retries, task.max_retries, exc)
                else:
                    task.status = TaskStatus.FAILED
                    self._record_result(
                        task,
                        TaskResult(status=TaskStatus.FAILED, error=str(exc), duration_ms=(time.monotonic() - start) * 1000),
                    )
                    logger.exception("Task %s failed permanently", task.name)

    def _run_periodic(self, task_name: str, handler: TaskHandler) -> None:
        try:
            task = Task(name=task_name)
            result = handler(task)
            self._record_result(task, result)
        except Exception:
            logger.exception("Periodic task %s failed", task_name)

    def _record_result(self, task: Task, result: TaskResult) -> None:
        with self._lock:
            self._task_results.append(
                {
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": result.status.value,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if len(self._task_results) > self._max_results:
                self._task_results = self._task_results[-self._max_results:]
