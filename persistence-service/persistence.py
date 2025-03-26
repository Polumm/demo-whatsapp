import json
import uuid
import logging
from datetime import datetime, timezone

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from aio_pika import IncomingMessage

from config import REDIS_HOST, REDIS_PORT, DATABASE_URL
from models import Message as DBMessage, Base

# Redis setup
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# PostgreSQL setup
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

async def store_message_in_redis(msg_data):
    cid = str(msg_data["conversation_id"])
    message_json = json.dumps(msg_data)
    redis_client.zadd(f"chat:{cid}:messages", {message_json: msg_data["sent_at"]})
    redis_client.zremrangebyrank(f"chat:{cid}:messages", 0, -101)

async def store_message_in_postgres(msg_data):
    db: Session = SessionLocal()
    try:
        dt_sent = datetime.fromtimestamp(msg_data["sent_at"], timezone.utc)
        new_msg = DBMessage(
            id=uuid.uuid4(),
            conversation_id=msg_data["conversation_id"],
            user_id=msg_data["sender_id"],
            content=msg_data.get("content"),
            type=msg_data["type"],
            sent_at=dt_sent,
        )
        db.add(new_msg)
        db.commit()
    finally:
        db.close()

async def on_persistence_message(msg: IncomingMessage):
    try:
        msg_data = json.loads(msg.body.decode())
        await store_message_in_redis(msg_data)
        await store_message_in_postgres(msg_data)
        await msg.ack()
        print(f"[persistence-service] Stored message: {msg_data}")
    except Exception as e:
        print(f"[persistence-service] Failed storing message: {e}")
