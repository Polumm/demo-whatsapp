import os

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_SECRET_KEY = os.getenv("ACCESS_SECRET_KEY", "access_secret_key")

CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "chat-service:8002")
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "auth-service:8003")
