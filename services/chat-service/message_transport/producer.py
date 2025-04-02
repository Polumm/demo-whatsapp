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
    Publish a message to our direct exchange with routing_key determined by presence.
    """
    to_user = message_dict.get("toUser")
    if not to_user:
        # e.g. group message scenario or broadcast
        await _publish_group_or_generic(message_dict)
        return

    # Determine which node the receiving user is on
    receiver_node_ids = await get_nodes_for_user(to_user)
    if not receiver_node_ids:
        # user offline or not found; handle offline scenario, store in DB, etc.
        logging.warning(f"[publish_message] No active devices found for user {to_user}")
        return

    try:
        # Use the persistent connection
        _, _, exchange = await get_publisher_connection()

        # Publish message
        body_str = json.dumps(message_dict)
        for node_id in receiver_node_ids:
            await exchange.publish(
                Message(body_str.encode("utf-8"), delivery_mode=DeliveryMode.PERSISTENT),
                routing_key=node_id,
            )
        # We do NOT close the connection—it's persistent!

    except Exception as e:
        # Optional: If you want to attempt a one-time reconnect, do so here:
        # logging.error("[publish_message] Error: %s. Retrying once...", e)
        # await force_reconnect()
        # then try again
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )


async def _publish_group_or_generic(message_dict: dict):
    """
    Handle group messages or messages that have no single 'toUser'.
    Possibly broadcast to each group member's node, etc.
    """
    conversation_id = message_dict["conversation_id"]
    members = await get_group_members(conversation_id)

    try:
        _, _, exchange = await get_publisher_connection()
        body_str = json.dumps(message_dict)

        for user_id in members:
            receiver_node_ids = await get_nodes_for_user(str(user_id))
            if not receiver_node_ids:
                continue

            for node_id in receiver_node_ids:
                await exchange.publish(
                    Message(body_str.encode("utf-8"), delivery_mode=DeliveryMode.PERSISTENT),
                    routing_key=node_id,
                )

    except Exception as e:
        logging.error("[_publish_group_or_generic] Error publishing group msg: %s", e)
