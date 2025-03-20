import os
import json
import redis
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    QUEUE_NAME,
    REDIS_HOST,
    REDIS_PORT,
    DATABASE_URL,
    PRESENCE_SERVICE_URL,
)
from models import Message, UsersConversation
import uuid
from datetime import datetime, timezone


engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency for database session management.
    Ensures connections are opened/closed properly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Redis connection
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


def create_consumer_connection():
    """
    (No longer used directly in code, unless you keep
     a fallback or handle certain edge cases.)
    You could remove this if you only use aio-pika now.
    """
    pass


async def get_node_for_user(user_id: str):
    """
    Query presence-service to find the node_id for a given user (async).
    Returns None if offline or not found.
    """
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{PRESENCE_SERVICE_URL}/presence/{user_id}")
            if r.status_code == 200:
                data = r.json()
                return data.get("node_id")  # e.g. "node-2"
            else:
                return None
    except Exception as e:
        print("[publish_message] Presence lookup error:", e)
        return None


async def store_message_in_redis(msg):
    """
    Stores a message in Redis using Sorted Sets (ZADD).
    Messages are sorted by 'sent_at' timestamp for efficient retrieval.
    """
    cid = str(msg["conversation_id"])
    message_json = json.dumps(msg)

    # Use 'sent_at' as the score
    redis_client.zadd(f"chat:{cid}:messages", {message_json: msg["sent_at"]})

    # Optional: remove older messages beyond some threshold
    redis_client.zremrangebyrank(f"chat:{cid}:messages", 0, -101)  # Keep last 100


async def get_recent_messages(conversation_id, count=50):
    """
    Fetches the last 'count' messages from Redis for a given conversation.
    Retrieves them in correct chronological order (oldest to newest).
    """
    messages = redis_client.zrange(f"chat:{conversation_id}:messages", -count, -1)
    return [json.loads(msg) for msg in messages]


async def get_messages_in_time_range(conversation_id, start_time, end_time):
    """
    Fetches messages from Redis in a specific time range (sorted by timestamp).
    """
    messages = redis_client.zrangebyscore(
        f"chat:{conversation_id}:messages",
        start_time,  # Start timestamp
        end_time,    # End timestamp
    )
    return [json.loads(msg) for msg in messages]


async def store_message_in_postgres(msg_data):
    """
    Stores the message in Postgres.
    """
    try:
        # Acquire a DB session
        db: Session = SessionLocal()
        dt_sent = datetime.fromtimestamp(msg_data["sent_at"], timezone.utc)

        # Build the Message object
        new_message = Message(
            id=uuid.uuid4(),
            conversation_id=msg_data["conversation_id"],
            user_id=msg_data["sender_id"],
            content=msg_data.get("content"),
            type=msg_data["type"],
            sent_at=dt_sent,
        )

        db.add(new_message)
        db.commit()
        db.close()
        print(f"[chat-consumer] Stored message in Postgres: {msg_data}")

    except Exception as e:
        print(f"[chat-consumer] Error storing message in Postgres: {e}")


def get_group_members(conversation_id: str):
    """
    Retrieves user_ids from the users_conversation table for the given conversation.
    """
    db: Session = SessionLocal()
    members = (
        db.query(UsersConversation.user_id)
        .filter(UsersConversation.conversation_id == conversation_id)
        .all()
    )
    db.close()
    # each row is a tuple like (UUID(...),), so we flatten:
    user_ids = [str(row[0]) for row in members]
    print(f"[chat-consumer] get_group_members({conversation_id}), found {user_ids}")
    return user_ids
