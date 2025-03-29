from typing import Optional, List
import uuid
import urllib.parse
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import httpx
from config import CHAT_SERVICE_URL
from dependencies import get_http_client, role_required, self_user_only

router = APIRouter()

class CreateConversationRequest(BaseModel):
    name: Optional[str] = None
    type: str  # "direct", "group", "channel"
    user_ids: List[uuid.UUID]

class ConversationMembersUpdate(BaseModel):
    user_ids: List[uuid.UUID]
    action: str  # "add" or "remove"


@router.post("/conversations")
async def create_conversation(
    payload: CreateConversationRequest,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    url = f"http://{CHAT_SERVICE_URL}/conversations"
    data = payload.model_dump()
    data["user_ids"] = [str(uid) for uid in data["user_ids"]]

    try:
        resp = await client.post(url, json=data)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")


@router.post("/conversations/{conversation_id}/members")
async def update_conversation_members(
    conversation_id: uuid.UUID,
    payload: ConversationMembersUpdate,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    url = f"http://{CHAT_SERVICE_URL}/conversations/{conversation_id}/members"
    data = payload.model_dump()
    data["user_ids"] = [str(uid) for uid in data["user_ids"]]

    try:
        resp = await client.post(url, json=data)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    url = f"http://{CHAT_SERVICE_URL}/conversations/{conversation_id}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")


@router.get("/conversations/{conversation_id}/messages")
async def get_paginated_messages(
    conversation_id: uuid.UUID,
    page: int = 1,
    size: int = 50,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    url = f"http://{CHAT_SERVICE_URL}/conversations/{conversation_id}/messages?page={page}&size={size}"
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")


@role_required("admin", "user")
@self_user_only("user_id")  # match query param name here
@router.get("/sync")
async def sync_user_messages(
    request: Request,
    user_id: str,
    since: float,
    conversations: Optional[List[str]] = None,
    client: httpx.AsyncClient = Depends(get_http_client)
):
    query_params = {
        "user_id": user_id,
        "since": str(since)
    }
    if conversations:
        query_params["conversations"] = conversations

    url = f"http://{CHAT_SERVICE_URL}/sync?{urllib.parse.urlencode(query_params, doseq=True)}"

    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.json()
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Chat service error: {str(e)}")
