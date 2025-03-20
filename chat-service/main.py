import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from models import Base
from dependencies import engine
from routes.conversations import router as convo_router
from publisher.publisher import router as websocket_router
from config import APP_ENV
from consumers.consumer import start_consumer


def create_tables():
    """Creates database tables only in development mode (avoid in production)."""
    if APP_ENV == "development":
        print("[chat-service] Running in development mode: Creating tables...")
        Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles app startup and shutdown lifecycle.
    """
    # Create tables only in development mode
    create_tables()

    # Start the consumer as a background task
    # so it runs in the same event loop
    print("[chat-service] Starting aio-pika consumer task...")
    app.state.consumer_task = asyncio.create_task(start_consumer())

    yield  # The app is running here

    # On shutdown, cancel the consumer task
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
