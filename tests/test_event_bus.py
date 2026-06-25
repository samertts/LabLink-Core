from __future__ import annotations

import asyncio
import threading

from app.events.base import Event, EventBus
from app.events.domain import (
    AlertRaised,
    DeviceConnected,
    DeviceDisconnected,
    DeviceRegistered,
    HealthChanged,
    ResultExported,
    ResultNormalized,
    ResultReceived,
    ResultStored,
    ResultValidated,
    SyncCompleted,
    SyncStarted,
)


class TestEventBase:
    def test_event_metadata_auto_generated(self) -> None:
        event = DeviceRegistered(device_id="D1")
        assert event.metadata.event_id
        assert event.metadata.timestamp
        assert event.metadata.version == 1

    def test_event_to_dict(self) -> None:
        event = DeviceRegistered(device_id="D1", vendor="Sysmex")
        d = event.to_dict()
        assert d["event_type"] == "device.registered"
        assert d["data"]["device_id"] == "D1"
        assert "metadata" in d

    def test_correlation_id(self) -> None:
        event = ResultReceived(device_id="D1", correlation_id="abc-123")
        assert event.metadata.correlation_id == "abc-123"

    def test_source(self) -> None:
        event = SyncStarted(source="ingest_service")
        assert event.metadata.source == "ingest_service"


class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("device.registered", lambda e: received.append(e))
        bus.publish(DeviceRegistered(device_id="D1"))
        assert len(received) == 1
        assert received[0].data["device_id"] == "D1"

    def test_wildcard_handler(self) -> None:
        bus = EventBus()
        received: list[Event] = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(DeviceRegistered(device_id="D1"))
        bus.publish(ResultReceived(device_id="D2"))
        assert len(received) == 2

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("device.registered", handler)
        bus.publish(DeviceRegistered(device_id="D1"))
        assert len(received) == 1
        bus.unsubscribe("device.registered", handler)
        bus.publish(DeviceRegistered(device_id="D2"))
        assert len(received) == 1

    def test_multiple_handlers(self) -> None:
        bus = EventBus()
        results = []
        bus.subscribe("device.registered", lambda e: results.append("a"))
        bus.subscribe("device.registered", lambda e: results.append("b"))
        bus.publish(DeviceRegistered(device_id="D1"))
        assert results == ["a", "b"]

    def test_handler_exception_does_not_break_others(self) -> None:
        bus = EventBus()
        results = []

        def bad_handler(e: Event) -> None:
            raise RuntimeError("boom")

        bus.subscribe("device.registered", bad_handler)
        bus.subscribe("device.registered", lambda e: results.append("ok"))
        bus.publish(DeviceRegistered(device_id="D1"))
        assert results == ["ok"]

    def test_publish_async(self) -> None:
        bus = EventBus()
        received: list[Event] = []

        async def handler(e: Event) -> None:
            received.append(e)

        bus.subscribe("device.registered", handler)
        asyncio.run(bus.publish_async(DeviceRegistered(device_id="D1")))
        assert len(received) == 1

    def test_history(self) -> None:
        bus = EventBus(max_history=5)
        for i in range(10):
            bus.publish(DeviceRegistered(device_id=f"D{i}"))
        history = bus.get_history()
        assert len(history) == 5
        assert history[0].data["device_id"] == "D5"

    def test_history_filter(self) -> None:
        bus = EventBus()
        bus.publish(DeviceRegistered(device_id="D1"))
        bus.publish(ResultReceived(device_id="D2"))
        history = bus.get_history(event_type="device.registered")
        assert len(history) == 1

    def test_clear_history(self) -> None:
        bus = EventBus()
        bus.publish(DeviceRegistered(device_id="D1"))
        bus.clear_history()
        assert bus.get_history() == []

    def test_interceptor(self) -> None:
        bus = EventBus()

        def add_tag(e: Event) -> Event:
            e.data["intercepted"] = True
            return e

        bus.add_interceptor(add_tag)
        received: list[Event] = []
        bus.subscribe("device.registered", lambda e: received.append(e))
        bus.publish(DeviceRegistered(device_id="D1"))
        assert received[0].data["intercepted"] is True

    def test_subscriber_count(self) -> None:
        bus = EventBus()
        bus.subscribe("device.registered", lambda e: None)
        bus.subscribe("device.registered", lambda e: None)
        assert bus.subscriber_count("device.registered") == 2
        assert bus.subscriber_count("result.received") == 0

    def test_thread_safety(self) -> None:
        bus = EventBus()
        results: list[str] = []
        lock = threading.Lock()

        def handler(e: Event) -> None:
            with lock:
                results.append(e.data["device_id"])

        bus.subscribe("device.registered", handler)

        def publish_many(prefix: str) -> None:
            for i in range(50):
                bus.publish(DeviceRegistered(device_id=f"{prefix}-{i}"))

        threads = [threading.Thread(target=publish_many, args=(f"T{t}",)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(results) == 200


class TestDomainEvents:
    def test_all_event_types(self) -> None:
        events = [
            DeviceConnected(device_id="D1"),
            DeviceDisconnected(device_id="D1"),
            DeviceRegistered(device_id="D1"),
            ResultReceived(device_id="D1"),
            ResultValidated(device_id="D1"),
            ResultNormalized(device_id="D1"),
            ResultStored(device_id="D1"),
            ResultExported(device_id="D1"),
            AlertRaised(severity="error", message="test"),
            SyncStarted(),
            SyncCompleted(sent=5, failed=0),
            HealthChanged(status="ok", checks={"db": "ok"}),
        ]
        for event in events:
            assert event.event_type
            d = event.to_dict()
            assert "event_type" in d
            assert "metadata" in d
