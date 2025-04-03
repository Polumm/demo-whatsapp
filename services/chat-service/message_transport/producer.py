import json
import logging
from typing import Optional
from fastapi import HTTPException
from aio_pika import connect_robust, Message, DeliveryMode, ExchangeType
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractChannel,
    AbstractExchange,
)
from config import RABBIT_HOST, RABBIT_PORT, EXCHANGE_NAME
from dependencies import get_group_members, get_node_map_for_users

publisher_connection: Optional[AbstractRobustConnection] = None
publisher_channel: Optional[AbstractChannel] = None
publisher_exchange: Optional[AbstractExchange] = None

async def get_publisher_connection():
    global publisher_connection, publisher_channel, publisher_exchange
    if not publisher_connection or publisher_connection.is_closed:
        logging.info("[RabbitMQ] Establishing a new publisher connection...")
        publisher_connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)
    if not publisher_channel or publisher_channel.is_closed:
        logging.info("[RabbitMQ] Establishing a new publisher channel...")
        publisher_channel = await publisher_connection.channel()
    if not publisher_exchange:
        logging.info("[RabbitMQ] Declaring the publisher exchange...")
        publisher_exchange = await publisher_channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
        )
    return publisher_connection, publisher_channel, publisher_exchange

async def distribute_message(message_dict: dict):
    """
    1) Determine recipient user_ids (self, 1-on-1, or group).
    2) Let presence-service do the node-level grouping (GET /presence/nodes).
    3) Publish one Node Message per node to RabbitMQ.
    """
    conversation_id = message_dict["conversation_id"]
    sender_id = message_dict["sender_id"]
    origin_device_id = message_dict.get("origin_device_id")
    to_user = message_dict.get("toUser")

    # Figure out all recipient user_ids
    if to_user == sender_id:
        # Self-sending
        all_recipients = {sender_id}
    elif to_user:
        # 1-on-1
        all_recipients = {sender_id, to_user}
    else:
        # Group chat
        members = await get_group_members(conversation_id)
        all_recipients = set(members)

    # Bulk node map call to presence-service
    node_map = await get_node_map_for_users(
        user_ids=list(all_recipients),
        sender_id=sender_id,
        origin_device_id=origin_device_id
    )

    if not node_map:
        logging.warning("[distribute_message] presence-service returned empty node_map.")
        return

    try:
        _, _, exchange = await get_publisher_connection()

        # node_map looks like: {"node1": [{"user_id":..., "device_id":...}, ...], "node2": [...]}
        for node_id, device_list in node_map.items():
            node_msg = {
                "event_type": "chat_message",
                "payload": message_dict,
                "target_devices": device_list
            }
            body_str = json.dumps(node_msg)

            await exchange.publish(
                Message(
                    body_str.encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT
                ),
                routing_key=node_id,
            )
        logging.debug(f"[distribute_message] Published message to {len(node_map)} node(s).")

    except Exception as e:
        logging.error("[distribute_message] Error publishing message: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error distributing message: {e}"
        )
