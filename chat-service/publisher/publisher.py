import json
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType

from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    EXCHANGE_NAME
)
from fastapi import HTTPException

from dependencies import get_node_for_user, get_group_members, update_presence_status


router = APIRouter()

# Track connected users on this node (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}

# the global connection variable
rabbit_connection = None

@router.websocket("/ws/{user_id}")
async def client_to_mq(websocket: WebSocket, user_id: str):
    """
    Main chat-service WebSocket endpoint.
    1) Accept connection from <gateway-service>.
    2) On each message, parse JSON and publish to RabbitMQ.
    3) The background consumer will deliver inbound messages (see consumers/consumer.py).
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
            print(f"[chat-service] Received from user {user_id}: {message_text}")

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
                message_dict["sent_at"] = datetime.now(timezone.utc).timestamp()

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

async def get_rabbit_connection():
    """Ensure a persistent RabbitMQ connection."""
    global rabbit_connection
    if rabbit_connection is None or rabbit_connection.is_closed:
        rabbit_connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)
    return rabbit_connection

async def publish_message(message_dict: dict):
    """
    Publish a message to our direct exchange with routing_key determined by presence.
    """
    to_user = message_dict.get("toUser")
    if not to_user:
        # e.g. group message scenario or broadcast
        await _publish_group_or_generic(message_dict)
        return

    # Determine which node the receiving user is on
    receiver_node_id = await get_node_for_user(to_user)
    if not receiver_node_id:
        # user offline or not found; handle offline scenario, store in DB, etc.
        print(f"[publish_message] User {to_user} is offline or not found.")
        return

    try:
        # Use the persistent connection
        connection = await get_rabbit_connection()
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
        )
        # Publish message
        body_str = json.dumps(message_dict)
        await exchange.publish(
            Message(
                body_str.encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT
            ),
            routing_key=receiver_node_id,
        )
        # Do not close the connection—it's persistent!
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error publishing message: {e}")



async def _publish_group_or_generic(message_dict: dict):
    """
    Handle group messages or messages that have no single 'toUser'.
    Possibly broadcast to each group member's node, etc.
    """
    conversation_id = message_dict["conversation_id"]
    members = get_group_members(conversation_id)

    try:
        # Use the persistent connection
        connection = await get_rabbit_connection()
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
        )

        for user_id in members:
            receiver_node_id = await get_node_for_user(str(user_id))
            if not receiver_node_id:
                # user offline
                continue

            body_str = json.dumps(message_dict)
            await exchange.publish(
                Message(
                    body_str.encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT
                ),
                routing_key=receiver_node_id,
            )
    except Exception as e:
        print("[_publish_group_or_generic] Error publishing group msg:", e)
