import pika
import json
import time
from dependencies import create_consumer_connection, redis_client
from services.notifications import send_push_notification
from routes.websocket import connected_users
from config import QUEUE_NAME


def store_in_redis(to_user, msg_data):
    """
    Simple example: store under 'chat:{to_user}:{timestamp}'.
    """
    key = f"chat:{to_user}:{msg_data['timestamp']}"
    redis_client.set(key, json.dumps(msg_data))
    print(f"[chat-consumer] ✅ Stored in Redis: {msg_data}")


def process_message(ch, method, properties, body):
    """
    Process a single RabbitMQ message: parse JSON, store in Redis, ack, etc.
    (Runs in the blocking pika callback.)
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

    # Attempt to store in Redis
    try:
        store_in_redis(to_user, msg_data)
        # Acknowledge only after successful store
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[chat-consumer] ✅ Acknowledged message for {to_user}")
    except Exception as e:
        print(f"[chat-consumer] ❌ Error storing in Redis: {e}")
        # No ack => message stays in the queue to be retried

    # If user is online, deliver in real-time.
    # (Optional) If you're doing real-time notifications in the consumer:
    if to_user in connected_users:
        ws = connected_users[to_user]
        # Because we're in a blocking thread, we can't await ws.send_text().
        # But you can schedule it on the main event loop if you want.
        # For a simple example, do a quick hacky approach:
        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(ws.send_text(json.dumps(msg_data)))
        loop.close()
        print(f"[chat-consumer] Delivered real-time to {to_user}.")
    else:
        # offline => push
        send_push_notification(to_user, msg_data)


def blocking_consume():
    """
    Runs a synchronous loop that connects to RabbitMQ, starts consuming,
    and reconnects on failure. Runs in a separate thread from FastAPI.
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
                auto_ack=False,
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
