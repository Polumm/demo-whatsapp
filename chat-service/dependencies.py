import json
import aioredis
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import UsersConversation
from config import (
    NODE_ID,
    REDIS_HOST,
    REDIS_PORT,
    DATABASE_URL,
    PRESENCE_SERVICE_URL,
)


# --- Async DB Engine Setup ---
async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# --- Async Redis Client ---
redis_pool = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True)


# --- Presence Lookup ---
async def get_node_for_user(user_id: str):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{PRESENCE_SERVICE_URL}/presence/{user_id}")
            if r.status_code == 200:
                data = r.json()
                return data.get("node_id")
            else:
                return None
    except Exception as e:
        print("[get_node_for_user] Presence lookup error:", e)
        return None


# --- Redis Message Store ---
async def store_message_in_redis(msg):
    cid = str(msg["conversation_id"])
    message_json = json.dumps(msg)
    score = msg["sent_at"]

    try:
        await redis_pool.zadd(f"chat:{cid}:messages", {message_json: score})
        await redis_pool.zremrangebyrank(f"chat:{cid}:messages", 0, -101)
    except Exception as e:
        print(f"[store_message_in_redis] Redis error: {e}")


# --- Fetch Messages from Redis ---
async def get_recent_messages(conversation_id, count=50):
    try:
        messages = await redis_pool.zrange(f"chat:{conversation_id}:messages", -count, -1)
        return [json.loads(m) for m in messages]
    except Exception as e:
        print(f"[get_recent_messages] Redis error: {e}")
        return []


async def get_messages_in_time_range(conversation_id, start_time, end_time):
    try:
        messages = await redis_pool.zrangebyscore(
            f"chat:{conversation_id}:messages",
            min=start_time,
            max=end_time
        )
        return [json.loads(m) for m in messages]
    except Exception as e:
        print(f"[get_messages_in_time_range] Redis error: {e}")
        return []


# --- Group Membership Lookup ---
async def get_group_members(conversation_id: str):
    async with AsyncSessionLocal() as session:
        stmt = select(UsersConversation.user_id).where(
            UsersConversation.conversation_id == conversation_id
        )
        result = await session.execute(stmt)
        members = result.scalars().all()
        user_ids = [str(uid) for uid in members]
        print(f"[get_group_members] Members of {conversation_id}: {user_ids}")
        return user_ids


# --- Presence Status Update ---
async def update_presence_status(user_id: str, status: str):
    payload = {"user_id": user_id, "node_id": NODE_ID, "status": status}
    url = (
        f"{PRESENCE_SERVICE_URL}/presence/online"
        if status == "online"
        else f"{PRESENCE_SERVICE_URL}/presence/offline"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print(f"[update_presence_status] {user_id} marked as {status}")
            else:
                print(f"[update_presence_status] Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"[update_presence_status] Error: {e}")
