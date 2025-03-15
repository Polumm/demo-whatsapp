import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "messages_queue")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_SECRET_KEY = os.getenv("ACCESS_SECRET_KEY", "access_secret_key")

# Database Config
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://chatuser:chatpass@postgres-chat:5432/chatdb"
)
