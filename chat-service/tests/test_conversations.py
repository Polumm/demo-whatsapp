import pytest
import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture(scope="session")
def setup_db():
    # If needed, ensure create_tables() is called. 
    # Or rely on the lifespan to do it. 
    yield
    # teardown if needed

def test_create_group_conversation(setup_db):
    payload = {
        "name": "My Group",
        "type": "group",
        "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
    }
    resp = client.post("/conversations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "group"
    convo_id = data["id"]

    # verify GET
    resp2 = client.get(f"/conversations/{convo_id}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["id"] == convo_id

def test_create_direct_conversation(setup_db):
    payload = {
        "type": "direct",
        "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
    }
    resp = client.post("/conversations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "direct"
    assert "id" in data
    
def test_update_conversation_members(setup_db):
    create_payload = {
        "name": "Team Chat",
        "type": "group",
        "user_ids": []
    }
    resp = client.post("/conversations", json=create_payload)
    assert resp.status_code == 200
    convo = resp.json()
    convo_id = convo["id"]

    # add
    update_payload = {
        "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        "action": "add"
    }
    resp2 = client.post(f"/conversations/{convo_id}/members", json=update_payload)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "updated"

    # remove
    remove_payload = {
        "user_ids": [update_payload["user_ids"][0]],
        "action": "remove"
    }
    resp3 = client.post(f"/conversations/{convo_id}/members", json=remove_payload)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "updated"
