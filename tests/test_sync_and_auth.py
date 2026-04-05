from fastapi.testclient import TestClient

from app.main import app
from app.security.auth import DEFAULT_API_KEY


def test_auth_required() -> None:
    client = TestClient(app)
    response = client.get("/devices")
    assert response.status_code == 401


def test_mode_and_sync_endpoints() -> None:
    client = TestClient(app)
    headers = {"x-api-key": DEFAULT_API_KEY}

    response = client.post("/mode", json={"mode": "hybrid"}, headers=headers)
    assert response.status_code == 200

    response = client.get("/mode", headers=headers)
    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"

    response = client.post("/edge/sync", headers=headers)
    assert response.status_code == 200
    assert "sent" in response.json()
