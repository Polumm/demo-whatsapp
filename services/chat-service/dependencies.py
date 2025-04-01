from datetime import datetime
import json
from redis.asyncio import Redis
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from models import UsersConversation, Message
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
redis_pool = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# --- Presence Lookup ---
async def get_nodes_for_user(user_id: str):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{PRESENCE_SERVICE_URL}/presence/{user_id}")
            if r.status_code == 200:
                data = r.json()  # should now be a list of device presence records
                return [entry["node_id"] for entry in data if entry.get("status") == "online"]
            else:
                return []
    except Exception as e:
        print("[get_nodes_for_user] Presence lookup error:", e)
        return []


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
async def update_presence_status(user_id: str, status: str, device_id: str):
    payload = {
        "user_id": user_id,
        "device_id": device_id,
        "node_id": NODE_ID,
        "status": status
    }
    url = (
        f"{PRESENCE_SERVICE_URL}/presence/online"
        if status == "online"
        else f"{PRESENCE_SERVICE_URL}/presence/offline"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print(f"[update_presence_status] {user_id}:{device_id} marked as {status}")
            else:
                print(f"[update_presence_status] Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"[update_presence_status] Error: {e}")


# --- Synchronize Messages from Redis or Redis + Postgres---
async def sync_messages(conversation_id: str, user_id: str, since: float, limit=100):
    # Step 1: Try Redis first
    redis_messages = await get_messages_in_time_range(conversation_id, since, end_time=9999999999)

    # Update "since" to latest message in Redis to avoid overlap
    try:
        latest_redis_ts = redis_messages[-1]["sent_at"]
    except (KeyError, TypeError, IndexError) as e:
        print(f"[sync_messages] Malformed Redis message: {e}")
        latest_redis_ts = since


    # Step 2: Query Postgres ONLY for messages newer than the latest Redis one
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.sent_at > datetime.fromtimestamp(latest_redis_ts))
            .order_by(Message.sent_at.asc())
            .limit(limit - len(redis_messages))
        )
        result = await session.execute(stmt)
        db_messages = result.scalars().all()

        db_formatted = [
            {
                "id": str(m.id),
                "conversation_id": str(m.conversation_id),
                "user_id": str(m.user_id),
                "content": m.content,
                "type": m.type,
                "sent_at": m.sent_at.timestamp()
            }
            for m in db_messages
        ]

    # Step 3: Combine the two — no overlap = no dedup needed
    combined = redis_messages + db_formatted
    combined.sort(key=lambda x: x["sent_at"])  # Optional: sort if needed

    return combined