import os
import redis.asyncio as redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

async def get_redis():
    """
    FastAPI dependency that yields an async Redis client.
    """
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    try:
        yield client
    finally:
        # Optional: close the connection when done
        await client.close()
