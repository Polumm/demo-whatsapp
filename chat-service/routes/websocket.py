import json
from typing import Dict
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from message_transport.producer import publish_message
from dependencies import update_presence_status

router = APIRouter()

# Track connected users on this node (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}


@router.websocket("/ws/{user_id}")
async def ws_client_server(websocket: WebSocket, user_id: str):
    """
    Main chat-service WebSocket endpoint that connect client with a server node.
    1) Accept connection from <gateway-service>.
    2) On each message from client, parse JSON and publish it to RabbitMQ.
    3) The background consumer will deliver messages from server nodes to clients.
        (see message_transport/consumer.py).
    """
    await websocket.accept()
    connected_users[user_id] = websocket
    print(f"[chat-service] User {user_id} connected via WebSocket.")

    # Update presence info
    await update_presence_status(user_id, "online")

    try:
        while True:
            # Read text from gateway => user is sending a chat message
            message_text = await websocket.receive_text()
            print(
                f"[chat-service] Received from user {user_id}: {message_text}"
            )

            # Parse JSON
            try:
                message_dict = json.loads(message_text)
            except json.JSONDecodeError:
                # If invalid JSON, just continue or optionally send an error
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
                message_dict["sent_at"] = datetime.now(
                    timezone.utc
                ).timestamp()

            # Publish to RabbitMQ asynchronously
            await publish_message(message_dict)

            # Optionally, echo back to confirm
            # await websocket.send_text("Message published!")

    except WebSocketDisconnect:
        print(f"[chat-service] User {user_id} disconnected.")
    finally:
        # Remove from connected list
        if user_id in connected_users:
            del connected_users[user_id]

        # Mark user as offline
        await update_presence_status(user_id, "offline")

        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        print(f"[chat-service] WebSocket closed for user {user_id}")
