import asyncio
import json
from datetime import datetime
from datetime import timezone
import os
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import requests
from dependencies import publish_message


PRESENCE_SERVICE_URL = os.getenv("PRESENCE_SERVICE_URL", "http://presence-service:8004")
NODE_ID = os.getenv("NODE_ID", "node-1")  # Set the correct node
router = APIRouter()

# Track connected users (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}

def update_presence_status(user_id: str, status: str):
    """
    Calls the presence-service API to update user status.
    """
    payload = {
        "user_id": user_id,
        "node_id": NODE_ID,
        "status": status
    }
    
    try:
        url = f"{PRESENCE_SERVICE_URL}/presence/online" if status == "online" else f"{PRESENCE_SERVICE_URL}/offline"
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"[presence-service] Updated presence for {user_id} to {status} on {NODE_ID}")
        else:
            print(f"[presence-service] Failed to update presence for {user_id}: {response.text}")
    except Exception as e:
        print(f"[presence-service] Error updating presence for {user_id}: {e}")


@router.websocket("/ws/{user_id}")
# @role_required("admin", "user")
async def chat_websocket(websocket: WebSocket, user_id: str):
    """
    The main chat-service WebSocket endpoint.
    1) Accept connection from <gateway-service>.
    2) On each message, parse JSON and publish to RabbitMQ (or store in DB).
    3) The background consumer (see below) will deliver inbound messages.
    """
    await websocket.accept()
    connected_users[user_id] = websocket
    print(f"[chat-service] User {user_id} connected via WebSocket.")

    # Update presence info
    update_presence_status(user_id, "online")
    
    try:
        while True:
            # Read text from gateway => user is sending a chat message
            message_text = await websocket.receive_text()
            print(f"[chat-service] Received from user {user_id}: {message_text}")

            # parse JSON
            try:
                message_dict = json.loads(message_text)
            except json.JSONDecodeError:
                # If invalid JSON, just continue or optionally do an error
                await websocket.send_text("Invalid JSON format.")
                continue

            # Ensure required fields. Override sender_id, set type & sent_at.
            if "conversation_id" not in message_dict:
                await websocket.send_text("Missing conversation_id.")
                continue
            
            # The server always trusts its own user_id
            message_dict["sender_id"] = user_id

            if "type" not in message_dict:
                message_dict["type"] = "text"

            if "sent_at" not in message_dict:
                message_dict["sent_at"] = datetime.now(timezone.utc).timestamp()
            
            # Publish to RabbitMQ
            await asyncio.get_event_loop().run_in_executor(
                None, publish_message, message_dict
            )

            # Optionally, echo back or do something immediate
            # await websocket.send_text("Message published!")
    except WebSocketDisconnect:
        print(f"[chat-service] User {user_id} disconnected.")
    finally:
        # remove from connected list
        if user_id in connected_users:
            del connected_users[user_id]
        
        # Mark user as offline
        update_presence_status(user_id, "offline")