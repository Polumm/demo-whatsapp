from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from dependencies import get_db
from models import Presence
import uuid

router = APIRouter()

class PresenceStatus(BaseModel):
    user_id: uuid.UUID
    node_id: str
    device_id: str
    status: str  # "online" or "offline"

@router.post("/online")
def user_online(payload: PresenceStatus, db: Session = Depends(get_db)):
    """
    Mark user as online.
    """
    if payload.status.lower() != "online":
        raise HTTPException(status_code=400, detail="Use status='online' or call /offline endpoint.")
    
    now_utc = datetime.now(timezone.utc)
    record = db.query(Presence).filter_by(user_id=payload.user_id, device_id=payload.device_id).first()

    if record:
        record.node_id = payload.node_id
        record.status = "online"
        record.last_online = now_utc
    else:
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            device_id=payload.device_id,
            status="online",
            last_online=now_utc
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return {"detail": "User is online"}

@router.post("/offline")
def user_offline(payload: PresenceStatus, db: Session = Depends(get_db)):
    """
    Mark user as offline.
    """
    if payload.status.lower() != "offline":
        raise HTTPException(status_code=400, detail="Use status='offline' or call /online endpoint.")

    now_utc = datetime.now(timezone.utc)
    record = db.query(Presence).filter_by(user_id=payload.user_id, device_id=payload.device_id).first()

    if not record:
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            device_id=payload.device_id,
            status="offline",
            last_online=now_utc
        )
        db.add(record)
    else:
        record.node_id = payload.node_id
        record.status = "offline"
        record.last_online = now_utc

    db.commit()
    return {"detail": "User is offline"}

class HeartbeatModel(BaseModel):
    user_id: uuid.UUID
    node_id: str
    device_id: str

@router.post("/heartbeat")
def heartbeat(payload: HeartbeatModel, db: Session = Depends(get_db)):
    """
    If you want a heartbeat approach to keep user as 'online'.
    """
    record = db.query(Presence).filter_by(user_id=payload.user_id).first()
    now_utc = datetime.now(timezone.utc)
    record = db.query(Presence).filter_by(user_id=payload.user_id, device_id=payload.device_id).first()

    if not record:
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            device_id=payload.device_id,
            status="online",
            last_online=now_utc
        )
        db.add(record)
    else:
        record.node_id = payload.node_id
        record.status = "online"
        record.last_online = now_utc

    db.commit()
    return {"detail": "Heartbeat updated"}

@router.get("/{user_id}")
def get_presence(user_id: str, db: Session = Depends(get_db)):
    """
    Returns presence record for a user.
    e.g. {status: 'online','offline', node_id:'...','last_online':...}
    """
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID")

    records = db.query(Presence).filter_by(user_id=user_uuid).all()
    if not records:
        raise HTTPException(status_code=404, detail="No presence record found")

    return [
        {
            "device_id": record.device_id,
            "node_id": record.node_id,
            "status": record.status,
            "last_online": record.last_online.isoformat()
        }
        for record in records
    ]
