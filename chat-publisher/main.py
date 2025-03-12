from fastapi import FastAPI, HTTPException
import uvicorn
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
from dependencies import publish_message

app = FastAPI()
executor = ThreadPoolExecutor()


class SendMessage(BaseModel):
    fromUser: str
    toUser: str
    content: str


@app.post("/send")
async def send_message(msg: SendMessage):
    """
    Accepts a message, publishes it to RabbitMQ, and returns immediately.
    """
    message_dict = {
        "fromUser": msg.fromUser,
        "toUser": msg.toUser,
        "content": msg.content,
        "timestamp": int(time.time() * 1000),
    }

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, publish_message, message_dict)

    return {"status": "Message published", "message": message_dict}


@app.get("/")
async def health_check():
    """Health check endpoint to confirm service is running."""
    return {"status": "chat-publisher OK"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
