from __future__ import annotations

from app.events.base import Event


class DeviceConnected(Event):
    event_type = "device.connected"


class DeviceDisconnected(Event):
    event_type = "device.disconnected"


class DeviceRegistered(Event):
    event_type = "device.registered"


class ResultReceived(Event):
    event_type = "result.received"


class ResultValidated(Event):
    event_type = "result.validated"


class ResultNormalized(Event):
    event_type = "result.normalized"


class ResultStored(Event):
    event_type = "result.stored"


class ResultExported(Event):
    event_type = "result.exported"


class AlertRaised(Event):
    event_type = "alert.raised"


class SyncStarted(Event):
    event_type = "sync.started"


class SyncCompleted(Event):
    event_type = "sync.completed"


class HealthChanged(Event):
    event_type = "health.changed"
