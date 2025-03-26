import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from models import Base

from dependencies import async_engine as engine

from routes.conversations import router as convo_router
from routes.websocket import router as websocket_router
from config import APP_ENV
from message_transport.consumer import consumer_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    if APP_ENV == "development":
        print("[chat-service] Running in development mode: Creating tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    print("[chat-service] Starting aio-pika consumer task...")
    app.state.consumer_task = asyncio.create_task(consumer_loop())

    yield

    print("[chat-service] Shutting down consumer task...")
    app.state.consumer_task.cancel()
    try:
        await app.state.consumer_task
    except asyncio.CancelledError:
        print("[chat-service] Consumer task cancelled.")


# Initialize FastAPI app with lifespan manager
app = FastAPI(lifespan=lifespan)
app.include_router(websocket_router)
app.include_router(convo_router)


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "chat-service OK"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
