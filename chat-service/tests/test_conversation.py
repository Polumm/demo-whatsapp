import pytest
import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture(scope="session")
def setup_db():
    """
    If needed, ensure DB tables exist or run migrations before tests.
    We do it at session scope so it's done once.
    In your code, you might call a function that ensures tables are created in dev mode,
    or do nothing if the app does it on startup.
    """
    print("[test_conversations] Setting up DB if needed...")
    # e.g. create_tables() if your app doesn't do it automatically in dev mode
    # or do nothing if your 'main.py' or 'startup event' does it.
    yield
    # teardown after all tests, if necessary

def test_create_group_conversation(setup_db):
    """
    Test creating a group chat.
    """
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

    # Verify GET
    resp2 = client.get(f"/conversations/{convo_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == convo_id
    assert resp2.json()["type"] == "group"

def test_create_direct_conversation(setup_db):
    """
    Test creating a direct 1-on-1 conversation.
    """
    payload = {
        "type": "direct",
        "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
    }
    resp = client.post("/conversations", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "direct"
    assert "id" in data

def test_create_conversation_invalid_type(setup_db):
    """
    Test creating a conversation with an invalid type => expect 400
    """
    payload = {
        "type": "invalid_type",
        "user_ids": [str(uuid.uuid4())]
    }
    resp = client.post("/conversations", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "Invalid conversation type" in data["detail"]

def test_create_direct_conversation_wrong_user_count(setup_db):
    """
    Test direct chat with a user count != 2 => expect 400
    """
    payload = {
        "type": "direct",
        "user_ids": [str(uuid.uuid4())]  # only one user
    }
    resp = client.post("/conversations", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert "Direct chat requires exactly 2 users" in data["detail"]

def test_update_conversation_members(setup_db):
    """
    Test adding and removing members from a group chat.
    """
    create_payload = {
        "name": "Team Chat",
        "type": "group",
        "user_ids": []
    }
    resp = client.post("/conversations", json=create_payload)
    assert resp.status_code == 200
    convo_id = resp.json()["id"]

    # Add Members
    update_payload = {
        "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
        "action": "add"
    }
    resp2 = client.post(f"/conversations/{convo_id}/members", json=update_payload)
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "updated"

    # Remove Members
    remove_payload = {
        "user_ids": [update_payload["user_ids"][0]],
        "action": "remove"
    }
    resp3 = client.post(f"/conversations/{convo_id}/members", json=remove_payload)
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "updated"
