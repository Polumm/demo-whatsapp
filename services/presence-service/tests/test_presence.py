import time
import pytest
import requests
import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture(scope="session")
def setup_db():
    # if your app auto-creates tables on startup, do nothing
    # else run migrations or create_tables()
    yield

def test_online(setup_db):
    user_uuid = uuid.uuid4()
    payload = {
        "user_id": str(user_uuid),
        "node_id": "chatservice-1",
        "status": "online"
    }

    resp = client.post("/presence/online", json=payload)
    assert resp.status_code == 200
    assert resp.json()["detail"] == "User is online"

    time.sleep(0.5)  # Ensures database update before GET request

    resp2 = client.get(f"/presence/{user_uuid}")
    assert resp2.status_code == 200

def test_offline(setup_db):
    user_uuid = uuid.uuid4()
    # Mark user as offline
    payload = {
        "user_id": str(user_uuid),
        "node_id": "chatservice-1",
        "status": "offline"
    }
    resp = client.post("/presence/offline", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detail"] == "User is offline"

    # check get
    resp2 = client.get(f"/presence/{user_uuid}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "offline"

def test_heartbeat(setup_db):
    user_uuid = uuid.uuid4()
    payload = {
        "user_id": str(user_uuid),
        "node_id": "chatservice-2"
    }
    resp = client.post("/presence/heartbeat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["detail"] == "Heartbeat updated"

    # check presence => should be 'online'
    resp2 = client.get(f"/presence/{user_uuid}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["status"] == "online"
    assert data2["node_id"] == "chatservice-2"
