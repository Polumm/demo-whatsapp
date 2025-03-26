import json
import uuid
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from aio_pika import IncomingMessage

from config import REDIS_HOST, REDIS_PORT, DATABASE_URL
from models import Message as DBMessage, Base

# Redis setup
redis = Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Async SQLAlchemy engine + session
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Optional: create tables once during startup (can also be done via Alembic)
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Store message in Redis
async def store_message_in_redis(msg_data):
    cid = str(msg_data["conversation_id"])
    message_json = json.dumps(msg_data)
    try:
        await redis.zadd(f"chat:{cid}:messages", {message_json: msg_data["sent_at"]})
        await redis.zremrangebyrank(f"chat:{cid}:messages", 0, -101)
    except Exception as e:
        print(f"[store_message_in_redis] Redis error: {e}")

# Store message in Postgres (async)
async def store_message_in_postgres(msg_data):
    async with AsyncSessionLocal() as session:
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
            session.add(new_msg)
            await session.commit()
        except Exception as e:
            print(f"[store_message_in_postgres] DB error: {e}")

# Message consumer callback
async def on_persistence_message(msg: IncomingMessage):
    try:
        msg_data = json.loads(msg.body.decode())
        await store_message_in_redis(msg_data)
        await store_message_in_postgres(msg_data)
        await msg.ack()
        print(f"[persistence-service] Stored message: {msg_data}")
    except Exception as e:
        print(f"[persistence-service] Failed storing message: {e}")
