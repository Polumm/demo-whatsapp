import json
import asyncio
import logging
from typing import Optional
from aio_pika import connect_robust, ExchangeType, IncomingMessage
from aio_pika.exceptions import AMQPConnectionError
from aio_pika.abc import (
    AbstractRobustConnection,
    AbstractChannel,
    AbstractExchange,
    AbstractQueue,
)

from dependencies import get_group_members
from routes.notifications import send_push_notification
from routes.websocket import connected_users
from fastapi.websockets import WebSocketState

from config import (
    EXCHANGE_NAME,
    NODE_ID,
    RABBIT_HOST,
    RABBIT_PORT,
)

# --- Connection globals ---
consumer_connection: Optional[AbstractRobustConnection] = None
consumer_channel: Optional[AbstractChannel] = None
consumer_exchange: Optional[AbstractExchange] = None
consumer_queue: Optional[AbstractQueue] = None


async def get_consumer_connection():
    global consumer_connection, consumer_channel, consumer_exchange, consumer_queue

    if not consumer_connection or consumer_connection.is_closed:
        logging.info("[chat-consumer] Establishing a new connection...")
        consumer_connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)

    if not consumer_channel or consumer_channel.is_closed:
        logging.info("[chat-consumer] Establishing a new channel...")
        consumer_channel = await consumer_connection.channel()

    if not consumer_exchange or consumer_exchange.is_closed:
        logging.info("[chat-consumer] Declaring the exchange...")
        consumer_exchange = await consumer_channel.declare_exchange(
            EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
        )

    if not consumer_queue or consumer_queue.is_closed:
        queue_name = f"{NODE_ID}-queue"
        logging.info("[chat-consumer] Declaring the queue: %s", queue_name)
        consumer_queue = await consumer_channel.declare_queue(queue_name, durable=True)
        logging.info("[chat-consumer] Binding queue to exchange with routing_key: %s", NODE_ID)
        await consumer_queue.bind(consumer_exchange, routing_key=NODE_ID)

    return consumer_connection, consumer_channel, consumer_exchange, consumer_queue


async def consumer_loop():
    retry_delay = 1
    while True:
        try:
            _, _, _, queue = await get_consumer_connection()
            logging.info("[chat-consumer] Waiting for messages...")
            await queue.consume(on_message, no_ack=False)
            await asyncio.Future()

        except asyncio.CancelledError:
            logging.info("[chat-consumer] Consumer task cancelled. Closing connection.")
            break
        except AMQPConnectionError as e:
            logging.error("[chat-consumer] RabbitMQ connection failed: %s. Retrying in %s seconds...", e, retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)
        except Exception as e:
            logging.error("[chat-consumer] Consumer crashed: %s", e)
            raise


async def on_message(message: IncomingMessage):
    msg_str = message.body.decode("utf-8")
    print(f"[chat-consumer] Received raw message: {msg_str}")

    try:
        msg_data = json.loads(msg_str)
    except json.JSONDecodeError as e:
        print("[chat-consumer] JSON parse error:", e)
        await message.ack()
        return

    to_user = msg_data.get("toUser")

    if to_user:
        # Direct chat: deliver to all devices
        sockets = connected_users.get(to_user)
        if sockets:
            for device_id, ws in sockets.items():
                await _deliver_message(ws, msg_data, to_user, device_id)
        else:
            await send_push_notification(to_user, msg_data)
    else:
        # Group chat: deliver to each member's devices
        participants = await get_group_members(msg_data["conversation_id"])
        for user_id in map(str, participants):
            sockets = connected_users.get(user_id)
            if sockets:
                for device_id, ws in sockets.items():
                    await _deliver_message(ws, msg_data, user_id, device_id)
            else:
                await send_push_notification(user_id, msg_data)

    await message.ack()


async def _deliver_message(ws, msg_data, user_id, device_id):
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.send_text(json.dumps(msg_data))
            print(f"[chat-consumer] Delivered to {user_id}:{device_id}")
        else:
            print(f"[chat-consumer] Skipped closed socket {user_id}:{device_id}")
    except Exception as e:
        print(f"[chat-consumer] Failed sending to {user_id}:{device_id} - {e}")
