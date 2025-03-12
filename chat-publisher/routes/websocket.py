from fastapi import APIRouter, WebSocket
import asyncio
import json

from dependencies import publish_message

router = APIRouter()


@router.websocket("/ws/send")
async def websocket_send(websocket: WebSocket):
    """
    WebSocket connection for sending messages to RabbitMQ in real-time.
    """
    await websocket.accept()
    print("[WebSocket] Connection established for sending messages.")

    try:
        while True:
            message_text = await websocket.receive_text()
            print(f"[WebSocket] Received message text: {message_text}")

            # 1) Parse the incoming text into a dict
            try:
                message_dict = json.loads(message_text)
            except json.JSONDecodeError:
                await websocket.send_text(
                    "Invalid JSON. Please send a JSON object."
                )
                continue

            # 2) Publish the Python dict directly
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, publish_message, message_dict)

            # 3) Send confirmation back to client
            await websocket.send_text("Message published!")
    except Exception as e:
        print(f"[WebSocket] Connection closed: {e}")
    finally:
        print("[WebSocket] WebSocket closed.")
