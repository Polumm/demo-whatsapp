# chat_service/schemas/conversations.py
from pydantic import BaseModel
from typing import List, Optional
import uuid

class ConversationCreate(BaseModel):
    name: Optional[str] = None
    type: str  # "direct" or "group"
    user_ids: List[uuid.UUID]

class ConversationMembersUpdate(BaseModel):
    user_ids: List[uuid.UUID]
    action: str  # "add" or "remove"

class ConversationOut(BaseModel):
    id: uuid.UUID
    name: Optional[str]
    type: str

    # for Pydantic 2.x
    model_config = {"from_attributes": True}  # Replaces orm_mode=True
