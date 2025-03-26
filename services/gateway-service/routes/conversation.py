from typing import Optional, List
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests
from config import CHAT_SERVICE_URL
from dependencies import role_required

router = APIRouter()

class CreateConversationRequest(BaseModel):
    name: Optional[str] = None  # Fix for Python 3.9
    type: str  # "direct", "group", "channel"
    user_ids: List[uuid.UUID]  # Fix for Python 3.9

class ConversationMembersUpdate(BaseModel):
    user_ids: List[uuid.UUID]  # Fix for Python 3.9
    action: str  # "add" or "remove"


@router.post("/conversations")
# @role_required("admin", "user")
def create_conversation(payload: CreateConversationRequest):
    """
    Forwards conversation creation request to the chat-service.
    """
    url = f"http://{CHAT_SERVICE_URL}/conversations"
    
    # Convert UUIDs to strings
    data = payload.model_dump()
    data["user_ids"] = [str(uid) for uid in data["user_ids"]]  # Fix UUID serialization issue

    try:
        resp = requests.post(url, json=data)
        if resp.status_code == 200:
            return resp.json()

        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail="Failed to reach chat-service")
    
    
@router.post("/conversations/{conversation_id}/members")
# @role_required("admin", "user")
def update_conversation_members(
    conversation_id: uuid.UUID, payload: ConversationMembersUpdate
):
    """
    Forwards membership updates to the chat-service.
    """
    url = f"http://{CHAT_SERVICE_URL}/conversations/{conversation_id}/members"
    
    # Convert UUIDs to strings before sending request
    data = payload.model_dump()
    data["user_ids"] = [str(uid) for uid in data["user_ids"]]

    resp = requests.post(url, json=data)
    
    if resp.status_code == 200:
        return resp.json()
    
    raise HTTPException(status_code=resp.status_code, detail=resp.text)


@router.get("/conversations/{conversation_id}")
# @role_required("admin", "user")
def get_conversation(conversation_id: uuid.UUID):
    """
    Fetch conversation details from chat-service.
    """
    url = f"http://{CHAT_SERVICE_URL}/conversations/{conversation_id}"
    resp = requests.get(url)
    if resp.status_code == 200:
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail=resp.text)
