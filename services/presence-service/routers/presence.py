from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Dict, List
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
    if payload.status.lower() != "online":
        raise HTTPException(status_code=400, detail="Use status='online' or call /offline.")
    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "online",
        "last_online": now_utc.isoformat()
    })
    # Optionally publish an event to a 'presence_updates' channel for real-time sync
    # await redis_client.publish("presence_updates", f"{str(payload.user_id)}:{payload.device_id}:online")
    return {"detail": "User/device is online"}

@router.post("/offline")
async def user_offline(payload: PresenceStatus, redis_client = Depends(get_redis)):
    if payload.status.lower() != "offline":
        raise HTTPException(status_code=400, detail="Use status='offline' or call /online.")
    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "offline",
        "last_online": now_utc.isoformat()
    })
    # Optionally publish an event to a 'presence_updates' channel
    # await redis_client.publish("presence_updates", f"{str(payload.user_id)}:{payload.device_id}:offline")
    return {"detail": "User/device is offline"}


@router.post("/heartbeat")
async def heartbeat(payload: PresenceStatus, redis_client = Depends(get_redis)):
    """
    Keep user/device as 'online' with a heartbeat.
    """
    now_utc = datetime.now(timezone.utc)
    user_key = f"presence:{str(payload.user_id)}"
    device_key = f"{user_key}:{payload.device_id}"
    await redis_client.sadd(f"{user_key}:devices", payload.device_id)
    await redis_client.hset(device_key, mapping={
        "node_id": payload.node_id,
        "device_id": payload.device_id,
        "status": "online",
        "last_online": now_utc.isoformat()
    })
    # Optionally publish presence_updates
    return {"detail": "Heartbeat updated (Redis only)"}


@router.get("/nodes")
async def get_presence_node_map(
    user_ids: str = Query(..., description="Comma-separated user IDs"),
    sender_id: str = Query(None, description="Optional sender user_id to exclude origin device"),
    origin_device_id: str = Query(None, description="Optional device_id to exclude if user_id=sender_id"),
    redis_client = Depends(get_redis)
) -> Dict[str, List[Dict[str, str]]]:
    """
    Bulk node-level grouping of presence data.
    Example request:
      GET /presence/nodes?user_ids=alice,bob,carol&sender_id=alice&origin_device_id=deviceX

    Returns a dict like:
      {
        "node1": [
          {"user_id": "alice", "device_id": "deviceA"},
          {"user_id": "bob",   "device_id": "device1"}
        ],
        "node2": [
          {"user_id": "carol", "device_id": "deviceC"}
        ]
      }

    The presence-service does all the grouping by node, so chat-service
    doesn't have to loop over everything.
    """
    user_ids_list = [u.strip() for u in user_ids.split(",") if u.strip()]

    # We'll accumulate node_id -> [ {user_id, device_id}, ... ]
    node_map = {}

    for raw_user_id in user_ids_list:
        # If your IDs are guaranteed to be UUID, you can validate here
        try:
            _ = uuid.UUID(raw_user_id)
        except ValueError:
            # if not a valid UUID, skip or raise
            continue

        user_key = f"presence:{raw_user_id}"
        device_set_key = f"{user_key}:devices"
        devices = await redis_client.smembers(device_set_key)
        if not devices:
            continue

        for device_id in devices:
            device_key = f"{user_key}:{device_id}"
            data = await redis_client.hgetall(device_key)
            if not data:
                continue

            # Only handle if status == 'online'
            if data.get("status") != "online":
                continue

            # Possibly exclude origin device if user==sender
            if (raw_user_id == sender_id) and (device_id == origin_device_id):
                continue

            node_id = data.get("node_id")
            if not node_id:
                continue

            if node_id not in node_map:
                node_map[node_id] = []
            node_map[node_id].append({
                "user_id": raw_user_id,
                "device_id": device_id
            })

    return node_map


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
