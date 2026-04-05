import asyncio

from app.edge.sync_engine import SyncEngine


async def _sender(_payload: dict) -> dict:
    return {"status": "ok"}


def test_sync_engine_conflict_resolution_and_sync() -> None:
    engine = SyncEngine()
    engine.stage(item_id="A", device_id="D1", payload={"x": 1}, version=1)
    engine.stage(item_id="A", device_id="D1", payload={"x": 2}, version=2)
    engine.stage(item_id="A", device_id="D1", payload={"x": 0}, version=1)

    assert engine.pending() == 1

    result = asyncio.run(engine.sync(_sender))
    assert result["sent"] == 1
    assert engine.pending() == 0
