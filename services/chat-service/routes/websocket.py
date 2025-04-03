import json
from typing import Dict
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from message_transport.producer import distribute_message
from dependencies import update_presence_status
from message_transport.persistor import send_to_persistence_queue

router = APIRouter()

# user_id -> {device_id -> WebSocket}
connected_users: Dict[str, Dict[str, WebSocket]] = {}

@router.websocket("/ws/{user_id}/{device_id}")
async def ws_client_server(websocket: WebSocket, user_id: str, device_id: str):
    """
    Main chat-service WebSocket endpoint that connects a client with this server node.

    - On each incoming message from the client, we parse JSON and:
      1) Persist it (enqueue to persistence).
      2) Distribute it to the appropriate recipients (1-on-1, group, or self).
    - The background consumer on each node receives the Node Messages from RabbitMQ
      and delivers them to local websockets.
    """
    await websocket.accept()

    if user_id not in connected_users:
        connected_users[user_id] = {}
    connected_users[user_id][device_id] = websocket
    print(f"[chat-service] User {user_id} connected from device {device_id}.")

    # Update presence info
    await update_presence_status(user_id, "online", device_id=device_id)

    try:
        while True:
            # Read text from gateway => user is sending a chat message
            message_text = await websocket.receive_text()
            print(f"[chat-service] Received from user {user_id}: {message_text}")
            # Parse JSON
            try:
                message_dict = json.loads(message_text)
            except json.JSONDecodeError:
                await websocket.send_text("Invalid JSON format.")
                continue

            # Ensure required fields. The server always trusts its own user_id
            if "conversation_id" not in message_dict:
                await websocket.send_text("Missing conversation_id.")
                continue
            message_dict["sender_id"] = user_id

            # Default type and sent_at if not provided
            if "type" not in message_dict:
                message_dict["type"] = "text"
            if "sent_at" not in message_dict:
                message_dict["sent_at"] = datetime.now(timezone.utc).timestamp()

            # Enqueue for database persistence
            await send_to_persistence_queue(message_dict)

            # The device that actually sent the message
            message_dict["origin_device_id"] = device_id

            # Unified distribution logic
            await distribute_message(message_dict)

    except WebSocketDisconnect:
        print(f"[chat-service] User {user_id} on device {device_id} disconnected.")
    finally:
        # Remove from connected list
        connected_users[user_id].pop(device_id, None)
        if not connected_users[user_id]:
            connected_users.pop(user_id)
        # Mark user/device offline
        await update_presence_status(user_id, "offline", device_id=device_id)

        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        print(f"[chat-service] WebSocket closed for {user_id}/{device_id}")
