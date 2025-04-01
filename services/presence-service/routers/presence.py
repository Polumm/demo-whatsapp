from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

from dependencies import get_redis

router = APIRouter()

class PresenceStatus(BaseModel):
    user_id: uuid.UUID
    node_id: str
    device_id: str
    status: str  # "online" or "offline"

@router.post("/online")
async def user_online(payload: PresenceStatus, redis_client = Depends(get_redis)):
    """
    Mark user/device as online in Redis.
    """
    if payload.status.lower() != "online":
        raise HTTPException(status_code=400, detail="Use status='online' or call /offline endpoint.")

    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"

    # 1) Add device_id to a set of devices for that user
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)

    # 2) Store presence data in a hash
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "online",
        "last_online": now_utc.isoformat()
    })

    return {"detail": "User/device is online"}

@router.post("/offline")
async def user_offline(payload: PresenceStatus, redis_client = Depends(get_redis)):
    """
    Mark user/device as offline in Redis.
    """
    if payload.status.lower() != "offline":
        raise HTTPException(status_code=400, detail="Use status='offline' or call /online endpoint.")

    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"

    # Make sure device is tracked
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)

    # Update the hash to offline
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "offline",
        "last_online": now_utc.isoformat()
    })

    return {"detail": "User/device is offline"}

class HeartbeatModel(BaseModel):
    user_id: uuid.UUID
    node_id: str
    device_id: str

@router.post("/heartbeat")
async def heartbeat(payload: HeartbeatModel, redis_client = Depends(get_redis)):
    """
    Keep user/device as 'online' with a heartbeat.
    """
    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"

    # Make sure device is tracked
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)

    # Update presence to 'online' again
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "online",
        "last_online": now_utc.isoformat()
    })

    return {"detail": "Heartbeat updated (Redis only)"}


@router.get("/{user_id}")
async def get_presence(user_id: str, redis_client = Depends(get_redis)):
    """
    Returns presence records for all devices for a given user_id.
    e.g. [{"device_id":..., "node_id":..., "status":..., "last_online":...}, ...]
    """
    # Validate user_id as UUID
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID")

    user_key = f"presence:{str(user_uuid)}"
    device_set_key = f"{user_key}:devices"

    # 1) Get all device_ids for this user
    devices = await redis_client.smembers(device_set_key)
    if not devices:
        raise HTTPException(status_code=404, detail="No presence record found for this user")

    records = []
    for device_id in devices:
        device_key = f"{user_key}:{device_id}"
        data = await redis_client.hgetall(device_key)
        if data:
            records.append({
                "device_id": data.get("device_id"),
                "node_id": data.get("node_id"),
                "status": data.get("status"),
                "last_online": data.get("last_online")
            })

    if not records:
        raise HTTPException(status_code=404, detail="No presence data found in Redis")

    return records
