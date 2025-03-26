import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", 5672))

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://chatuser:chatpass@postgres-chat:5432/chatdb"
)

EXCHANGE_NAME = "persistence-exchange"
QUEUE_NAME = "persistence-queue"
ROUTING_KEY = "store"
