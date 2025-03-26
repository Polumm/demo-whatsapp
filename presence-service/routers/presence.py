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
    status: str  # "online" or "offline"

@router.post("/online")
def user_online(payload: PresenceStatus, db: Session = Depends(get_db)):
    if payload.status.lower() != "online":
        raise HTTPException(status_code=400, detail="Use status='online' or call /offline endpoint.")

    record = db.query(Presence).filter_by(user_id=payload.user_id).first()
    now_utc = datetime.now(timezone.utc)

    if record:
        record.node_id = payload.node_id
        record.status = "online"
        record.last_online = now_utc
    else:
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            status="online",
            last_online=now_utc
        )
        db.add(record)

    db.commit()  # Ensures the record is stored
    db.refresh(record)  # Ensures latest data is available immediately

    return {"detail": "User is online"}


@router.post("/offline")
def user_offline(payload: PresenceStatus, db: Session = Depends(get_db)):
    """
    Mark user as offline.
    """
    if payload.status.lower() != "offline":
        raise HTTPException(status_code=400, detail="Use status='offline' or call /online endpoint.")
    
    record = db.query(Presence).filter_by(user_id=payload.user_id).first()
    if not record:
        # create record with offline? or error
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            status="offline",
        )
        db.add(record)
    else:
        record.node_id = payload.node_id
        record.status = "offline"
        record.last_online = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "User is offline"}

class HeartbeatModel(BaseModel):
    user_id: uuid.UUID
    node_id: str
    # optional timestamp

@router.post("/heartbeat")
def heartbeat(payload: HeartbeatModel, db: Session = Depends(get_db)):
    """
    If you want a heartbeat approach to keep user as 'online'.
    """
    record = db.query(Presence).filter_by(user_id=payload.user_id).first()
    now_utc = datetime.now(timezone.utc)
    if not record:
        record = Presence(
            user_id=payload.user_id,
            node_id=payload.node_id,
            status="online",
            last_online=now_utc
        )
        db.add(record)
    else:
        record.node_id = payload.node_id
        record.status = "online"  # refresh status
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
    
    record = db.query(Presence).filter_by(user_id=user_uuid).first()
    if not record:
        raise HTTPException(status_code=404, detail="No presence record found")

    return {
        "user_id": str(record.user_id),
        "node_id": record.node_id,
        "status": record.status,
        "last_online": record.last_online.isoformat()
    }
