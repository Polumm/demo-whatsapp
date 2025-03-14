import asyncio
import json
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from dependencies import publish_message

router = APIRouter()

# Track connected users (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}


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

            # Possibly add a timestamp
            # message_dict["timestamp"] = int(time.time() * 1000)

            # Publish to RabbitMQ (or store in DB)
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