import os

RABBIT_HOST = os.getenv("RABBIT_HOST", "rabbitmq")
RABBIT_PORT = int(os.getenv("RABBIT_PORT", "5672"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "messages_queue")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_SECRET_KEY = os.getenv("ACCESS_SECRET_KEY", "access_secret_key")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8003")
