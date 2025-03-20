import json
import asyncio
import logging
from aio_pika import connect_robust, ExchangeType, IncomingMessage
from aio_pika.exceptions import AMQPConnectionError

from dependencies import get_group_members
from dependencies import store_message_in_redis, store_message_in_postgres
from routes.notifications import send_push_notification
from publisher.publisher import connected_users

from config import (
    EXCHANGE_NAME,
    NODE_ID,
    RABBIT_HOST,
    RABBIT_PORT,
)

async def start_consumer():
    """
    Establishes an aio-pika connection, declares the queue, and starts consuming.
    Retries the connection if RabbitMQ is not yet available.
    """
    retry_delay = 1  # start with 1 second delay
    while True:
        try:
            connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)
            channel = await connection.channel()

            # Declare exchange & queue
            exchange = await channel.declare_exchange(
                EXCHANGE_NAME, ExchangeType.DIRECT, durable=True
            )
            queue_name = f"{NODE_ID}-queue"
            queue = await channel.declare_queue(queue_name, durable=True)

            # Bind queue to exchange with routing_key=NODE_ID
            await queue.bind(exchange, routing_key=NODE_ID)

            logging.info("[chat-consumer] Waiting for messages (aio-pika consume)...")

            # Start consuming with a message handler
            await queue.consume(on_message, no_ack=False)

            # Keep the task alive; this future never completes unless cancelled.
            await asyncio.Future()

        except asyncio.CancelledError:
            logging.info("[chat-consumer] Consumer task cancelled. Closing connection.")
            break
        except AMQPConnectionError as e:
            logging.error("[chat-consumer] RabbitMQ connection failed: %s. Retrying in %s seconds...", e, retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 30)  # exponential backoff capped at 30 seconds
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
    await _storage_tasks(msg_data)

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


async def _storage_tasks(msg_data):
    """
    Stores message in Redis & Postgres concurrently.
    """
    try:
        await store_message_in_redis(msg_data)
        print("[chat-consumer] Successfully stored message in Redis.")
    except Exception as e:
        print("[chat-consumer] Redis store error:", e)

    try:
        await store_message_in_postgres(msg_data)
        print("[chat-consumer] Successfully stored message in Postgres.")
    except Exception as e:
        print("[chat-consumer] Postgres store error:", e)
