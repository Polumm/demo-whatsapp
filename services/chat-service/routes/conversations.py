from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from dependencies import get_db
from models import Conversation, UsersConversation
from schemas.conversations import (
    ConversationCreate,
    ConversationMembersUpdate,
    ConversationOut,
)

router = APIRouter()


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    payload: ConversationCreate, db: AsyncSession = Depends(get_db)
):
    if payload.type not in ["direct", "group", "channel"]:
        raise HTTPException(status_code=400, detail="Invalid conversation type")

    if payload.type == "direct":
        if len(payload.user_ids) != 2:
            raise HTTPException(status_code=400, detail="Direct chat requires exactly 2 users")

        stmt = (
            select(Conversation)
            .join(UsersConversation, Conversation.id == UsersConversation.conversation_id)
            .where(
                UsersConversation.user_id.in_(payload.user_ids),
                Conversation.type == "direct"
            )
            .group_by(Conversation.id)
            .having(func.count(UsersConversation.user_id) == 2)
        )
        result = await db.execute(stmt)
        existing_convo = result.scalars().first()
        if existing_convo:
            return existing_convo

    convo = Conversation(name=payload.name, type=payload.type)
    db.add(convo)
    await db.flush()  # Get convo.id

    memberships = [
        UsersConversation(user_id=user_id, conversation_id=convo.id, role_in_convo="member")
        for user_id in payload.user_ids
    ]
    db.add_all(memberships)

    await db.commit()
    await db.refresh(convo)
    return convo


@router.post("/conversations/{conversation_id}/members")
async def update_conversation_members(
    conversation_id: uuid.UUID,
    payload: ConversationMembersUpdate,
    db: AsyncSession = Depends(get_db),
):
    convo = await db.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.action == "add":
        stmt = select(UsersConversation.user_id).where(UsersConversation.conversation_id == conversation_id)
        result = await db.execute(stmt)
        existing_users = {row[0] for row in result.all()}

        new_users = [uid for uid in payload.user_ids if uid not in existing_users]
        if new_users:
            memberships = [
                UsersConversation(user_id=uid, conversation_id=conversation_id, role_in_convo="member")
                for uid in new_users
            ]
            db.add_all(memberships)

    elif payload.action == "remove":
        stmt = delete(UsersConversation).where(
            UsersConversation.user_id.in_(payload.user_ids),
            UsersConversation.conversation_id == conversation_id
        )
        await db.execute(stmt)

    else:
        raise HTTPException(status_code=400, detail="Invalid action (use 'add' or 'remove')")

    await db.commit()
    return {"status": "updated"}


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    convo = await db.get(Conversation, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return convo


async def get_user_conversations(user_id: str, db: AsyncSession) -> list[str]:
    """
    Returns all conversation IDs the user is part of.
    """
    stmt = select(UsersConversation.conversation_id).where(
        UsersConversation.user_id == uuid.UUID(user_id)
    )
    result = await db.execute(stmt)
    conversation_ids = result.scalars().all()

    return [str(cid) for cid in conversation_ids]