import json
import logging
from typing import Optional
from fastapi import HTTPException, APIRouter
from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractChannel,
    AbstractExchange,
)

from config import RABBIT_HOST, RABBIT_PORT, EXCHANGE_NAME

from dependencies import get_nodes_for_user, get_group_members

router = APIRouter()


# Global references
publisher_connection: Optional[AbstractRobustConnection] = None
publisher_channel: Optional[AbstractChannel] = None
publisher_exchange: Optional[AbstractExchange] = None


async def get_publisher_connection():
    """
    Ensure a persistent RabbitMQ connection, channel, and exchange for publishing.
    Re-connect if necessary. Stores references in module-level globals.
    """
    global publisher_connection, publisher_channel, publisher_exchange

    # If no connection or it is closed, create a new one
    if not publisher_connection or publisher_connection.is_closed:
        logging.info("[RabbitMQ] Establishing a new publisher connection...")
        publisher_connection = await connect_robust(
            host=RABBIT_HOST, port=RABBIT_PORT
        )

    # If no channel or it is closed, create a new one
    if not publisher_channel or publisher_channel.is_closed:
        logging.info("[RabbitMQ] Establishing a new publisher channel...")
        publisher_channel = await publisher_connection.channel()

    # If no exchange or it is closed, declare a new one
    # (Strictly speaking, Exchange objects don't always have 'is_closed',
    #  but you might want to re-declare if your channel got re-opened.)
    if not publisher_exchange:
        logging.info("[RabbitMQ] Declaring the publisher exchange...")
        publisher_exchange = await publisher_channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
        )

    return publisher_connection, publisher_channel, publisher_exchange


async def publish_message(message_dict: dict):
    """
    Publishes a message to the appropriate node(s) using RabbitMQ routing.
    Handles both direct and group messages.
    """
    to_user = message_dict.get("toUser")
    sender_id = message_dict.get("sender_id")

    # Group case
    if not to_user:
        await _publish_group(message_dict)
        return

    # Direct self-message? Skip if already delivered locally
    if to_user == sender_id:
        logging.info("[publish_message] Skipping self-message publish, handled locally.")
        return

    receiver_node_ids = await get_nodes_for_user(to_user)
    if not receiver_node_ids:
        logging.warning(f"[publish_message] No active devices found for user {to_user}")
        return

    try:
        _, _, exchange = await get_publisher_connection()
        body_str = json.dumps(message_dict)

        for node_id in receiver_node_ids:
            await exchange.publish(
                Message(body_str.encode("utf-8"), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=node_id,
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )



async def _publish_group(message_dict: dict):
    """
    Publishes group messages to each member's active nodes.
    Adds 'toUser' dynamically per user for correct consumer routing.
    Skips the sender to avoid redundant delivery.
    """
    conversation_id = message_dict["conversation_id"]
    sender_id = message_dict.get("sender_id")
    members = await get_group_members(conversation_id)

    try:
        _, _, exchange = await get_publisher_connection()

        for user_id in members:
            # Skip sending to self — consumer will handle it if needed
            if str(user_id) == str(sender_id):
                continue

            receiver_node_ids = await get_nodes_for_user(str(user_id))
            if not receiver_node_ids:
                logging.info(f"[_publish_group] No active node for user {user_id}")
                continue

            # Add toUser for routing logic on consumer
            message_for_user = message_dict.copy()
            message_for_user["toUser"] = str(user_id)
            body_str = json.dumps(message_for_user)

            for node_id in receiver_node_ids:
                await exchange.publish(
                    Message(body_str.encode("utf-8"), delivery_mode=DeliveryMode.PERSISTENT),
                    routing_key=node_id,
                )

    except Exception as e:
        logging.error("[_publish_group] Error publishing group msg: %s", e)
