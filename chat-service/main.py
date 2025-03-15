import uvicorn
import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
import os

from models import Base
from dependencies import engine
from routes.conversations import router as convo_router
from routes.websocket import router as websocket_router
from consumers.consumer import blocking_consume, set_main_loop

# Get environment mode
APP_ENV = os.getenv("APP_ENV", "development")

def create_tables():
    """Creates database tables only in development mode (avoid in production)."""
    if APP_ENV == "development":
        print("[chat-service] Running in development mode: Creating tables...")
        Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles app startup and shutdown lifecycle."""
    # Set event loop for consumer (if needed)
    loop = asyncio.get_running_loop()
    set_main_loop(loop)

    # Create tables only in development mode
    create_tables()

    # Prevent multiple consumer threads
    if "consumer_thread" not in globals():
        global consumer_thread
        consumer_thread = threading.Thread(target=blocking_consume, daemon=True)
        consumer_thread.start()
        print("[chat-service] blocking_consume started in background thread.")

    yield  # Runs while the app is running

    print("[chat-service] Shutting down...")

# Initialize FastAPI app with lifespan manager
app = FastAPI(lifespan=lifespan)
app.include_router(websocket_router)
app.include_router(convo_router, tags=["conversations"])

@app.get("/")
def health_check():
    """Health check endpoint."""
    return {"status": "chat-service OK"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
