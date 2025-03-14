import pika
import json
import time
import asyncio

from dependencies import create_consumer_connection, redis_client
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
def store_in_redis(to_user, msg_data):
    """
    Simple example: store under 'chat:{to_user}:{timestamp}' in Redis.
    """
    key = (
        f"chat:{to_user}:{msg_data.get('timestamp', int(time.time() * 1000))}"
    )
    redis_client.set(key, json.dumps(msg_data))
    print(f"[chat-consumer] Stored in Redis: {msg_data}")


def process_message(ch, method, properties, body):
    """
    Parse JSON, store in Redis, ack if successful.
    If user is online, schedule a coroutine to deliver real-time on MAIN_LOOP.
    """
    msg_str = body.decode("utf-8")
    print(f"[chat-consumer] Received raw message: {msg_str}")

    try:
        msg_data = json.loads(msg_str)
        print(f"[chat-consumer] Parsed message: {msg_data}")
    except json.JSONDecodeError as e:
        print("[chat-consumer] JSON parse error:", e)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    to_user = msg_data.get("toUser")

    # If user is online, schedule real-time delivery
    if to_user in connected_users:
        ws = connected_users[to_user]
        # Schedule the async send on the main event loop via run_coroutine_threadsafe
        if MAIN_LOOP:
            future = asyncio.run_coroutine_threadsafe(
                _deliver_message(ws, msg_data), MAIN_LOOP
            )
            # future.result()  # Not necessary; we can let it run in background
        else:
            print(
                "[chat-consumer] Warning: MAIN_LOOP not set, can't deliver real-time."
            )
    else:
        # If offline => push
        send_push_notification(to_user, msg_data)

    # Attempt to store in Redis
    try:
        store_in_redis(to_user, msg_data)
        # Acknowledge only after successful store
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[chat-consumer] Acknowledged message for {to_user}")
    except Exception as e:
        print(f"[chat-consumer] Error storing in Redis: {e}")
        # No ack => message remains in queue for retry


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
