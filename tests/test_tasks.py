from __future__ import annotations

import threading
import time

from app.tasks.worker import BackgroundWorker, Task, TaskResult, TaskStatus


class TestTask:
    def test_task_defaults(self) -> None:
        task = Task(name="test")
        assert task.task_id
        assert task.status == TaskStatus.PENDING
        assert task.retries == 0


class TestBackgroundWorker:
    def test_enqueue_and_process(self) -> None:
        worker = BackgroundWorker(poll_interval=0.05)
        worker.register_handler("echo", lambda t: TaskResult(status=TaskStatus.COMPLETED, data=t.payload.get("msg")))
        worker.start()
        task = Task(name="echo", payload={"msg": "hello"})
        worker.enqueue(task)
        time.sleep(0.3)
        worker.stop()
        assert worker.get_results()
        assert worker.get_results()[0]["status"] == "completed"

    def test_no_handler_records_failure(self) -> None:
        worker = BackgroundWorker(poll_interval=0.05)
        worker.start()
        worker.enqueue(Task(name="unknown"))
        time.sleep(0.2)
        worker.stop()
        results = worker.get_results()
        assert results
        assert results[0]["status"] == "failed"

    def test_retry_on_failure(self) -> None:
        worker = BackgroundWorker(poll_interval=0.05, max_retries=2)
        call_count = [0]

        def flaky(t: Task) -> TaskResult:
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("transient")
            return TaskResult(status=TaskStatus.COMPLETED)

        worker.register_handler("flaky", flaky)
        worker.start()
        worker.enqueue(Task(name="flaky"))
        time.sleep(0.5)
        worker.stop()
        assert call_count[0] == 3

    def test_periodic_task(self) -> None:
        worker = BackgroundWorker(poll_interval=0.05)
        count = [0]

        def tick(t: Task) -> TaskResult:
            count[0] += 1
            return TaskResult(status=TaskStatus.COMPLETED)

        worker.register_periodic("tick", tick, interval_seconds=0.1)
        worker.start()
        time.sleep(0.4)
        worker.stop()
        assert count[0] >= 2

    def test_start_stop(self) -> None:
        worker = BackgroundWorker()
        assert not worker.is_running
        worker.start()
        assert worker.is_running
        worker.stop()
        assert not worker.is_running

    def test_queue_size(self) -> None:
        worker = BackgroundWorker()
        assert worker.queue_size() == 0
        worker.enqueue(Task(name="a"))
        assert worker.queue_size() == 1

    def test_thread_safety(self) -> None:
        worker = BackgroundWorker(poll_interval=0.01)
        worker.register_handler("x", lambda t: TaskResult(status=TaskStatus.COMPLETED))
        worker.start()

        def enqueue_many() -> None:
            for _ in range(25):
                worker.enqueue(Task(name="x"))

        threads = [threading.Thread(target=enqueue_many) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        time.sleep(0.5)
        while worker.queue_size() > 0:
            time.sleep(0.1)
        time.sleep(0.3)
        worker.stop()
        results = worker.get_results()
        assert len(results) == 100, f"Expected 100, got {len(results)}"
