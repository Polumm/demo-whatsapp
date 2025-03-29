from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from typing import List, Optional
from dependencies import get_db, sync_messages
from routes.conversations import  get_user_conversations
from models import Message

router = APIRouter()


@router.get("/conversations/{conversation_id}/messages")
async def get_paginated_messages(
    conversation_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated messages for a conversation.
    Page numbers start from 1. Each page returns 'size' messages.
    Most recent messages come first.
    """
    offset = (page - 1) * size

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sent_at.desc())
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(stmt)
    messages = result.scalars().all()

    # Optional: Format messages for return
    return [
        {
            "id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "user_id": str(m.user_id),
            "content": m.content,
            "type": m.type,
            "sent_at": m.sent_at.isoformat(),
        }
        for m in messages
    ]


@router.get("/sync")
async def sync_user_messages(
    user_id: str,
    since: float = Query(..., description="Last seen timestamp (Unix)"),
    conversations: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync unread messages for user.
    Checks Redis first, then Postgres if needed.
    """
    synced = []

    conv_ids = conversations or await get_user_conversations(user_id, db)
    for cid in conv_ids:
        try:
            messages = await sync_messages(cid, user_id, since)
            synced.append({
                "conversation_id": cid,
                "messages": messages
            })
        except Exception as e:
            print(f"[sync_user_messages] Error syncing {cid}: {e}")
            continue

    return {"synced": synced}