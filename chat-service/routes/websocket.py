from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict

router = APIRouter()

# Track connected users (user_id -> WebSocket)
connected_users: Dict[str, WebSocket] = {}


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await websocket.accept()
    connected_users[user_id] = websocket
    print(f"[chat-consumer] User {user_id} connected.")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"[chat-consumer] User {user_id} disconnected.")
        del connected_users[user_id]
