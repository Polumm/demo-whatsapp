import pika
import asyncio
import json
from datetime import datetime
from datetime import timezone
from typing import Dict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import requests
from config import PRESENCE_SERVICE_URL
from config import NODE_ID
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
)
from fastapi import HTTPException
from config import EXCHANGE_NAME

from dependencies import get_node_for_user
from dependencies import get_group_members


router = APIRouter()

# Track connected users on this node (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}


@router.websocket("/ws/{user_id}")
# @role_required("admin", "user")
async def client_to_mq(websocket: WebSocket, user_id: str):
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
            print(
                f"[chat-service] Received from user {user_id}: {message_text}"
            )

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
                message_dict["sent_at"] = datetime.now(
                    timezone.utc
                ).timestamp()

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

        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        print(f"[chat-service] WebSocket closed for user {user_id}")


def publish_message(message_dict):
    """
    Publish a message to the direct exchange. We determine the target user's node
    and set that as the routing_key. If user offline, you can store or skip.
    """
    to_user = message_dict.get("toUser")
    if not to_user:
        # e.g. group message scenario or error
        _publish_group_or_generic(message_dict)
        return

    receiver_node_id = get_node_for_user(to_user)
    if not receiver_node_id:
        # user offline or not found in presence
        # handle offline scenario, store for later, etc.
        print(f"[publish_message] User {to_user} is offline or not found.")
        # Or just store in DB, or do nothing, up to you
        return

    try:
        parameters = pika.ConnectionParameters(
            host=RABBIT_HOST, port=RABBIT_PORT
        )
        with pika.BlockingConnection(parameters) as connection:
            channel = connection.channel()
            # we do NOT declare queue here, only declare exchange if needed
            channel.exchange_declare(
                exchange=EXCHANGE_NAME, exchange_type="direct", durable=True
            )

            # Publish to the exchange with routing_key=receiver_node_id
            body_str = json.dumps(message_dict)
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=receiver_node_id,
                body=body_str.encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )


def _publish_group_or_generic(message_dict):
    """
    Example of how you'd handle group messages or messages that have no single 'toUser'.
    Possibly you'd broadcast to each group member's node, etc.
    You can either loop over each user in the group and do the same presence logic,
    or store it for them to fetch next time.
    """
    # For a group scenario, you'd get the group membership from DB, then for each user:

    conversation_id = message_dict["conversation_id"]
    members = get_group_members(conversation_id)

    for user_id in members:
        receiver_node_id = get_node_for_user(str(user_id))
        if not receiver_node_id:
            # user offline
            continue
        try:
            parameters = pika.ConnectionParameters(
                host=RABBIT_HOST, port=RABBIT_PORT
            )
            with pika.BlockingConnection(parameters) as connection:
                channel = connection.channel()
                channel.exchange_declare(
                    exchange=EXCHANGE_NAME,
                    exchange_type="direct",
                    durable=True,
                )
                body_str = json.dumps(message_dict)
                channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=receiver_node_id,
                    body=body_str.encode("utf-8"),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
        except Exception as e:
            print("[_publish_group_or_generic] Error publishing group msg:", e)


def update_presence_status(user_id: str, status: str):
    """
    Calls the presence-service API to update user status.
    """
    payload = {"user_id": user_id, "node_id": NODE_ID, "status": status}

    try:
        url = (
            f"{PRESENCE_SERVICE_URL}/presence/online"
            if status == "online"
            else f"{PRESENCE_SERVICE_URL}/presence/offline"
        )
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(
                f"[presence-service] Updated presence for {user_id} to {status} on {NODE_ID}"
            )
        else:
            print(
                f"[presence-service] Failed to update presence for {user_id}: {response.text}"
            )
    except Exception as e:
        print(f"[presence-service] Error updating presence for {user_id}: {e}")
