import os

# RabbitMQ Config
RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "chat-direct-exchange")
NODE_ID = os.getenv("NODE_ID", "node-1")  # Each instance should have a unique NODE_ID
QUEUE_NAME = f"{NODE_ID}-queue"  # Per-node queue

# Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Authentication Config
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_SECRET_KEY = os.getenv("ACCESS_SECRET_KEY", "access_secret_key")

# Database Config
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://chatuser:chatpass@postgres-chat:5432/chatdb"
)

# Presence Service URL
PRESENCE_SERVICE_URL = os.getenv("PRESENCE_SERVICE_URL", "http://presence-service:8004")
