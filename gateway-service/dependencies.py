import pika
import json
from fastapi import HTTPException
from config import RABBIT_HOST, RABBIT_PORT, QUEUE_NAME


def publish_message(message_dict):
    """Publishes a message to RabbitMQ."""
    try:
        with pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBIT_HOST, port=RABBIT_PORT)
        ) as connection:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            # message_dict is a dict => we do a single json.dumps here
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(message_dict).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )
