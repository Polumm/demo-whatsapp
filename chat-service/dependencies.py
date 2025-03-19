import os
import json
import pika
import requests
import redis
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    QUEUE_NAME,
    REDIS_HOST,
    REDIS_PORT,
)
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from sqlalchemy.orm import Session
from models import Message
import uuid
from sqlalchemy.orm import Session
from models import UsersConversation
from datetime import datetime
from datetime import timezone

# Exchange name
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "chat-direct-exchange")
NODE_ID = os.getenv("NODE_ID", "node-1")  # local node ID if we need it
PRESENCE_URL = (
    "http://presence-service:8004"  # or whatever your presence-service is
)

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
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
)


def create_consumer_connection():
    """Creates a dedicated RabbitMQ connection for the consumer."""
    connection_params = pika.ConnectionParameters(
        host=RABBIT_HOST, port=RABBIT_PORT
    )
    return pika.BlockingConnection(connection_params)


def get_node_for_user(user_id: str):
    """
    Query presence-service to find the node_id for a given user.
    Returns None if offline or not found.
    """
    try:
        # GET /presence-service/<user_id>
        r = requests.get(f"{PRESENCE_URL}/presence/{user_id}")
        if r.status_code == 200:
            data = r.json()
            return data.get("node_id")  # e.g. "node-2"
        else:
            return None
    except Exception as e:
        print("[publish_message] Presence lookup error:", e)
        return None


def publish_message(message_dict):
    """
    Publish a message to the direct exchange. We determine the target user's node
    and set that as the routing_key. If user offline, you can store or skip.
    """
    to_user = message_dict.get("toUser")
    if not to_user:
        # e.g. group message scenario or error
        _publish_group_or_generic(message_dict)
        return

    user_node_id = get_node_for_user(to_user)
    if not user_node_id:
        # user offline or not found in presence
        # handle offline scenario, store for later, etc.
        print(f"[publish_message] User {to_user} is offline or not found.")
        # Or just store in DB, or do nothing, up to you
        return

    try:
        parameters = pika.ConnectionParameters(
            host=RABBIT_HOST, port=RABBIT_PORT
        )
        with pika.BlockingConnection(parameters) as connection:
            channel = connection.channel()
            # we do NOT declare queue here, only declare exchange if needed
            channel.exchange_declare(
                exchange=EXCHANGE_NAME, exchange_type="direct", durable=True
            )

            # Publish to the exchange with routing_key=user_node_id
            body_str = json.dumps(message_dict)
            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=user_node_id,
                body=body_str.encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )


def _publish_group_or_generic(message_dict):
    """
    Example of how you'd handle group messages or messages that have no single 'toUser'.
    Possibly you'd broadcast to each group member's node, etc.
    You can either loop over each user in the group and do the same presence logic,
    or store it for them to fetch next time.
    """
    # For a group scenario, you'd get the group membership from DB, then for each user:
    from .dependencies import get_group_members

    conversation_id = message_dict["conversation_id"]
    members = get_group_members(conversation_id)

    for user_id in members:
        user_node_id = get_node_for_user(str(user_id))
        if not user_node_id:
            # user offline
            continue
        try:
            parameters = pika.ConnectionParameters(
                host=RABBIT_HOST, port=RABBIT_PORT
            )
            with pika.BlockingConnection(parameters) as connection:
                channel = connection.channel()
                channel.exchange_declare(
                    exchange=EXCHANGE_NAME,
                    exchange_type="direct",
                    durable=True,
                )
                body_str = json.dumps(message_dict)
                channel.basic_publish(
                    exchange=EXCHANGE_NAME,
                    routing_key=user_node_id,
                    body=body_str.encode("utf-8"),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
        except Exception as e:
            print("[_publish_group_or_generic] Error publishing group msg:", e)


async def store_message_in_redis(msg):
    """
    Stores a message in Redis using Sorted Sets (ZADD).
    Messages are sorted by 'sent_at' timestamp for efficient retrieval.
    """
    cid = str(msg["conversation_id"])
    message_json = json.dumps(msg)

    # Use 'sent_at' as the score to ensure messages are sorted by time
    redis_client.zadd(f"chat:{cid}:messages", {message_json: msg["sent_at"]})

    # Optional: Remove older messages beyond a threshold (e.g., keep last 100)
    redis_client.zremrangebyrank(
        f"chat:{cid}:messages", 0, -101
    )  # Keeps last 100 messages


async def get_recent_messages(conversation_id, count=50):
    """
    Fetches the last 'count' messages from Redis for a given conversation.
    Retrieves them in correct chronological order (oldest to newest).
    """
    messages = redis_client.zrange(
        f"chat:{conversation_id}:messages", -count, -1
    )  # Get latest 'count' messages
    return [
        json.loads(msg) for msg in messages
    ]  # Convert JSON back to Python dict


async def get_messages_in_time_range(conversation_id, start_time, end_time):
    """
    Fetches messages from Redis in a specific time range (sorted by timestamp).
    """
    messages = redis_client.zrangebyscore(
        f"chat:{conversation_id}:messages",
        start_time,  # Start timestamp
        end_time,  # End timestamp
    )
    return [json.loads(msg) for msg in messages]


async def store_message_in_postgres(msg_data):
    """
    Stores the message in Postgres.
    """
    try:
        db: Session = next(get_db())  # Get a DB session
        dt_sent = datetime.fromtimestamp(msg_data["sent_at"], timezone.utc)
        new_message = Message(
            id=uuid.uuid4(),
            conversation_id=msg_data["conversation_id"],
            user_id=msg_data["sender_id"],
            content=msg_data["content"],
            type=msg_data["type"],
            sent_at=dt_sent,
        )

        db.add(new_message)
        db.commit()
        print(f"[chat-consumer] Stored message in Postgres: {msg_data}")

    except Exception as e:
        print(f"[chat-consumer] Error storing message in Postgres: {e}")


def get_group_members(conversation_id: str):
    """
    Retrieves user_ids from the users_conversation table for the given conversation.
    """
    db: Session = next(get_db())  # yields a session
    members = (
        db.query(UsersConversation.user_id)
        .filter(UsersConversation.conversation_id == conversation_id)
        .all()
    )  # returns list of (user_id,)

    # each row is a tuple like (UUID(...),), so we flatten:
    user_ids = [row[0] for row in members]
    db.close()
    print(
        f"[chat-consumer] get_group_members called for {conversation_id}, found {user_ids}"
    )
    return user_ids
