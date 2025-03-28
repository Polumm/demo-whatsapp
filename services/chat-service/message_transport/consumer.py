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

from message_transport.persistor import send_to_persistence_queue
from dependencies import get_group_members
from routes.notifications import send_push_notification
from routes.websocket import connected_users

from config import (
    EXCHANGE_NAME,
    NODE_ID,
    RABBIT_HOST,
    RABBIT_PORT,
)

# the global connection variable
consumer_connection: Optional[AbstractRobustConnection] = None
consumer_channel: Optional[AbstractChannel] = None
consumer_exchange: Optional[AbstractExchange] = None
consumer_queue: Optional[AbstractQueue] = None

async def get_consumer_connection():
    """
    Ensure a persistent RabbitMQ connection for the consumer.
    This includes the connection, channel, exchange, and queue.
    """
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
    """
    Establishes an aio-pika connection, declares the queue (and binds it),
    and starts consuming. Retries the connection if RabbitMQ is not yet available
    using exponential backoff.
    """
    retry_delay = 1  # start with 1 second
    while True:
        try:
            _, channel, exchange, queue = await get_consumer_connection()
            
            logging.info("[chat-consumer] Waiting for messages (aio-pika consume)...")
            await queue.consume(on_message, no_ack=False)

            # Keep the task alive; if we exit, consumer stops.
            await asyncio.Future()  # This future never completes unless cancelled

        except asyncio.CancelledError:
            logging.info("[chat-consumer] Consumer task cancelled. Closing connection.")
            break
        except AMQPConnectionError as e:
            logging.error(
                "[chat-consumer] RabbitMQ connection failed: %s. Retrying in %s seconds...", 
                e, retry_delay
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)  # exponential backoff up to 30s
        except Exception as e:
            logging.error("[chat-consumer] Consumer crashed: %s", e)
            raise


async def on_message(message: IncomingMessage):
    """
    Handler for incoming messages from RabbitMQ.
    1) Parse JSON
    2) Real-time deliver (direct or group)
    3) Store in Redis/Postgres
    4) Acknowledge
    """
    msg_str = message.body.decode("utf-8")
    print(f"[chat-consumer] Received raw message: {msg_str}")

    # parse JSON
    try:
        msg_data = json.loads(msg_str)
    except json.JSONDecodeError as e:
        print("[chat-consumer] JSON parse error:", e)
        # Safely acknowledge so it won't requeue
        await message.ack()
        return

    # Real-time delivery
    to_user = msg_data.get("toUser")
    if to_user:
        # direct chat
        ws = connected_users.get(to_user)
        if ws is not None:
            await _deliver_message(ws, msg_data)
        else:
            # offline => push
            await send_push_notification(to_user, msg_data)
    else:
        # group scenario => membership
        participants = get_group_members(msg_data["conversation_id"])
        # broadcast
        await _group_broadcast(participants, msg_data)

    # Store message in Redis, Postgres concurrently
    await send_to_persistence_queue(msg_data)

    # Acknowledge last, so if something fails we can retry
    await message.ack()


async def _deliver_message(ws, msg_data):
    """
    Coroutine that sends the message to the user's WebSocket.
    """
    try:
        await ws.send_text(json.dumps(msg_data))
        print(f"[chat-consumer] Delivered real-time to {msg_data.get('toUser')}.")
    except Exception as e:
        print("[chat-consumer] Failed sending to WebSocket:", e)


async def _group_broadcast(participants, msg_data):
    """Broadcast a message to each group member if connected, else push."""
    for p in participants:
        p_str = str(p)
        if p_str in connected_users:
            ws = connected_users[p_str]
            await _deliver_message(ws, msg_data)
        else:
            await send_push_notification(p_str, msg_data)