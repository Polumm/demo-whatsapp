from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
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
def create_conversation(
    payload: ConversationCreate, db: Session = Depends(get_db)
):
    """
    Create a new conversation:
    - "direct" (between 2 users)
    - "group" (multiple users)
    - "channel" (broadcast mode)
    """
    if payload.type not in ["direct", "group", "channel"]:
        raise HTTPException(
            status_code=400, detail="Invalid conversation type"
        )

    # Ensure exactly 2 users for direct chats
    if payload.type == "direct":
        if len(payload.user_ids) != 2:
            raise HTTPException(
                status_code=400, detail="Direct chat requires exactly 2 users"
            )

        # Prevent duplicate direct conversations
        existing_convo = (
            db.query(Conversation)
            .select_from(Conversation)
            .join(
                UsersConversation,
                Conversation.id
                == UsersConversation.conversation_id,  # ON condition
            )
            .filter(
                UsersConversation.user_id.in_(payload.user_ids),
                Conversation.type == "direct",
            )
            .group_by(Conversation.id)
            .having(func.count(UsersConversation.user_id) == 2)
            .first()
        )

        if existing_convo:
            return existing_convo  # Return existing chat instead of creating a new one

    # Create the conversation
    convo = Conversation(name=payload.name, type=payload.type)
    db.add(convo)
    db.flush()  # so convo.id is available

    memberships = [
        UsersConversation(
            user_id=user_id, conversation_id=convo.id, role_in_convo="member"
        )
        for user_id in payload.user_ids
    ]
    db.bulk_save_objects(memberships)

    db.commit()
    db.refresh(convo)
    return convo


@router.post("/conversations/{conversation_id}/members")
def update_conversation_members(
    conversation_id: uuid.UUID,
    payload: ConversationMembersUpdate,
    db: Session = Depends(get_db),
):
    """
    Add/remove members for a conversation.
    Direct chats are usually static, but we allow member modifications for flexibility.
    """
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if payload.action == "add":
        # Avoid adding duplicates
        existing_users = {
            m.user_id
            for m in db.query(UsersConversation.user_id)
            .filter_by(conversation_id=conversation_id)
            .all()
        }
        new_users = [
            uid for uid in payload.user_ids if uid not in existing_users
        ]

        if new_users:
            memberships = [
                UsersConversation(
                    user_id=uid,
                    conversation_id=conversation_id,
                    role_in_convo="member",
                )
                for uid in new_users
            ]
            db.bulk_save_objects(memberships)

    elif payload.action == "remove":
        db.query(UsersConversation).filter(
            UsersConversation.user_id.in_(payload.user_ids),
            UsersConversation.conversation_id == conversation_id,
        ).delete(synchronize_session=False)

    else:
        raise HTTPException(
            status_code=400, detail="Invalid action (use 'add' or 'remove')"
        )

    db.commit()
    return {"status": "updated"}


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID, db: Session = Depends(get_db)
):
    """
    Fetch conversation details, including its members.
    """
    convo = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return convo
