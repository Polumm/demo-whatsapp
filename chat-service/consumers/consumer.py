import pika
import json
import time
import asyncio

from dependencies import create_consumer_connection, get_group_members
from dependencies import store_message_in_redis, store_message_in_postgres
from services.notifications import send_push_notification
from routes.websocket import connected_users
from config import QUEUE_NAME

###########################
# Global reference to main event loop
###########################
MAIN_LOOP = None  # We will set this at startup in main.py


def set_main_loop(loop: asyncio.AbstractEventLoop):
    """
    Called once at application startup, so the consumer code knows which
    event loop to schedule coroutines on. This avoids the "no current event loop" error.
    """
    global MAIN_LOOP
    MAIN_LOOP = loop
    print("[chat-consumer] MAIN_LOOP set successfully.")


###########################
# The main logic
###########################

def process_message(ch, method, properties, body):
    """
    1) Parse JSON
    2) If direct => toUser? If group => membership?
    3) Acknowledge
    4) Real-time deliver
    5) Store in Redis, Postgres asynchronously
    """

    msg_str = body.decode("utf-8")
    print(f"[chat-consumer] Received raw message: {msg_str}")

    # parse JSON
    try:
        msg_data = json.loads(msg_str)
    except json.JSONDecodeError as e:
        print("[chat-consumer] JSON parse error:", e)
        if method is not None:
            ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # Acknowledge
    if method is not None:
        ch.basic_ack(delivery_tag=method.delivery_tag)
    else:
        print("[chat-consumer] WARNING: method is None, cannot ack")

    # Real-time delivery
    to_user = msg_data.get("toUser")
    if to_user:
        # direct chat
        ws = connected_users.get(to_user)
        if ws and MAIN_LOOP:
            future = asyncio.run_coroutine_threadsafe(_deliver_message(ws, msg_data), MAIN_LOOP)
        else:
            # offline => push
            if MAIN_LOOP:
                asyncio.run_coroutine_threadsafe(send_push_notification(to_user, msg_data), MAIN_LOOP)
    else:
        # group scenario => membership
        participants = get_group_members(msg_data["conversation_id"])
        # let's do a function for real-time broadcast
        async def group_broadcast():
            for p in participants:
                if p in connected_users:
                    await _deliver_message(connected_users[p], msg_data)
                else:
                    await send_push_notification(p, msg_data)

        if MAIN_LOOP:
            asyncio.run_coroutine_threadsafe(group_broadcast(), MAIN_LOOP)

    # now do the storage tasks
    async def storage_tasks():
        try:
            await store_message_in_redis(msg_data)
        except Exception as e:
            print("[chat-consumer] Redis store error:", e)

        try:
            await store_message_in_postgres(msg_data)
        except Exception as e:
            print("[chat-consumer] Postgres store error:", e)

    if MAIN_LOOP:
        asyncio.run_coroutine_threadsafe(storage_tasks(), MAIN_LOOP)
    else:
        print("[chat-consumer] WARNING: no MAIN_LOOP, can't do storage tasks")


###########################
# The async routine for real-time delivery
###########################
async def _deliver_message(ws, msg_data):
    """
    Coroutine that sends the message to the user's WebSocket.
    Scheduled from the blocking thread using run_coroutine_threadsafe(...).
    """
    try:
        await ws.send_text(json.dumps(msg_data))
        print(
            f"[chat-consumer] Delivered real-time to {msg_data.get('toUser')}."
        )
    except Exception as e:
        print("[chat-consumer] Failed sending to WebSocket:", e)


###########################
# The main blocking consumer loop
###########################
def blocking_consume():
    """
    Connects to RabbitMQ, starts a blocking consume, auto-reconnect on failure.
    This runs in a separate thread from FastAPI.
    """
    retry_delay = 1
    while True:
        try:
            print("[chat-consumer] Connecting to RabbitMQ for consumption...")
            connection = create_consumer_connection()
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_message,
                auto_ack=False,  # We do manual ack in process_message
            )

            print("[chat-consumer] Waiting for messages (blocking consume)...")
            channel.start_consuming()  # BLOCKS this thread

        except pika.exceptions.AMQPConnectionError as e:
            print(
                f"[chat-consumer] RabbitMQ connection lost: {e}. Retrying in {retry_delay}s..."
            )
            time.sleep(retry_delay)
            retry_delay = min(
                retry_delay * 2, 30
            )  # Exponential backoff up to 30s
        except Exception as e:
            print("[chat-consumer] Consumer crashed:", e, "Retrying in 5s...")
            time.sleep(5)


# def get_group_members(conversation_id: str):
#     """
#     Placeholder function for group membership. In real code, you'd query DB or a cache.
#     """
#     print("[chat-consumer] get_group_members called.")
#     return ["Bob", "Charlie", "Dave"]  # example
