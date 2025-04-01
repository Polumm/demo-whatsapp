import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.websockets import WebSocketState
from config import CHAT_SERVICE_URL
import websockets
from dependencies import role_required, self_user_only

router = APIRouter()


@router.websocket("/ws/{user_id}")
@role_required("admin", "user")
@self_user_only("user_id")
async def websocket_proxy(websocket: WebSocket, user_id: str, device_id: str = Query(...)):
    """
    WebSocket Proxy in gateway-service.
    Connects to chat-service's WebSocket and relays traffic in both directions.
    """
    chat_ws_url = f"ws://{CHAT_SERVICE_URL}/ws/{user_id}/{device_id}"
    print(f"[gateway] Connecting to chat-service WebSocket: {chat_ws_url}")

    await websocket.accept()

    try:
        # Connect to internal chat-service WebSocket
        async with websockets.connect(chat_ws_url) as chat_ws:
            print(f"[gateway] Connected to chat-service for user {user_id} from device {device_id}")

            async def client_to_chat():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await chat_ws.send(data)
                except Exception as e:
                    print(f"[client_to_chat] Error: {e}")
                    # await chat_ws.close()
                    # raise

            async def chat_to_client():
                try:
                    while True:
                        msg = await chat_ws.recv()
                        await websocket.send_text(msg)
                except Exception as e:
                    print(f"[chat_to_client] Error: {e}")
                    # await websocket.close()
                    # raise

            # Run both forwarding tasks concurrently
            task1 = asyncio.create_task(client_to_chat())
            task2 = asyncio.create_task(chat_to_client())

            # Wait for either task to exit (disconnect or error)
            done, pending = await asyncio.wait(
                {task1, task2}, return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

    except WebSocketDisconnect:
        print(f"[gateway] Client WebSocket disconnected: user_id={user_id}, device_id={device_id}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"[gateway] Chat-service connection closed unexpectedly for user_id={user_id}, device_id={device_id}: {e}")
    except Exception as e:
        print(f"[gateway] Unexpected proxy error for user_id={user_id}, device_id={device_id}: {e}")
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        print(f"[gateway] Proxy closed for user_id={user_id}, device_id={device_id}")
