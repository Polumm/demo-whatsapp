import pika
import redis
from config import RABBIT_HOST, RABBIT_PORT, REDIS_HOST, REDIS_PORT

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
