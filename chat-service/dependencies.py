import jwt
import json
import pika
import redis
from functools import wraps
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    QUEUE_NAME,
    REDIS_HOST,
    REDIS_PORT,
    ACCESS_SECRET_KEY,
    ALGORITHM,
)
from fastapi import Request, WebSocket, HTTPException
from typing import Optional
from fastapi import HTTPException

# Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
)


def create_consumer_connection():
    """Creates a dedicated RabbitMQ connection for the consumer."""
    connection_params = pika.ConnectionParameters(
        host=RABBIT_HOST, port=RABBIT_PORT
    )
    return pika.BlockingConnection(connection_params)


def publish_message(message_dict):
    """Publishes a message to RabbitMQ. A blocking call used in a thread pool."""
    try:
        parameters = pika.ConnectionParameters(
            host=RABBIT_HOST, port=RABBIT_PORT
        )
        with pika.BlockingConnection(parameters) as connection:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(message_dict).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )
            # Optionally, channel.close() is called automatically by "with ..."

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )
