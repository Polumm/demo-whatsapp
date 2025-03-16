import asyncio
import requests
import websockets
from config import CHAT_SERVICE_URL
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from dependencies import role_required

router = APIRouter()


@router.websocket("/ws/{user_id}")
# @role_required("admin", "user")
async def websocket_proxy(websocket: WebSocket, user_id: str):
    """
    WebSocket Proxy in `gateway-service`.
    1) Authenticates user (if you have a decorator or inline logic).
    2) Connects to the internal chat-service WebSocket route => ws://chat-service:8002/ws/{user_id}.
    3) Forwards messages from the client -> chat-service.
    4) Forwards messages from chat-service -> client, concurrently.
    """
    chat_ws_url = f"ws://{CHAT_SERVICE_URL}/ws/{user_id}"
    print(f"[gateway] Connecting to chat-service WebSocket: {chat_ws_url}")

    await websocket.accept()  # Accept the gateway WebSocket

    try:
        # Connect to the chat-service WebSocket
        async with websockets.connect(chat_ws_url) as chat_ws:
            print(f"[gateway] Successfully connected to {chat_ws_url}")

            # Task A: forward from user -> chat-service
            async def forward_from_client_to_chat():
                while True:
                    data = await websocket.receive_text()
                    await chat_ws.send(data)

            # Task B: forward from chat-service -> user
            async def forward_from_chat_to_client():
                while True:
                    response = await chat_ws.recv()
                    await websocket.send_text(response)

            # Run both tasks concurrently until one fails or disconnects
            await asyncio.gather(
                forward_from_client_to_chat(), forward_from_chat_to_client()
            )

    except WebSocketDisconnect:
        print(f"[gateway] WebSocket disconnected: user_id={user_id}")
    except Exception as e:
        print(f"[gateway] Proxy error for user {user_id}: {e}")
    finally:
        # We'll close both sides if we can
        await websocket.close()
        print(f"[gateway] Proxy closed for user {user_id}")
