import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "messages_queue")
