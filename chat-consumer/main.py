from fastapi import FastAPI
import uvicorn
import threading
from contextlib import asynccontextmanager

from routes.websocket import router as websocket_router
from consumers.consumer import blocking_consume


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This runs at startup and shutdown, replacing the deprecated @app.on_event("startup")
    """
    # Start the blocking consumer in a separate thread
    thread = threading.Thread(target=blocking_consume, daemon=True)
    thread.start()
    print("[chat-consumer] Background consumer thread started.")

    yield  # Yield control to FastAPI (application is running)

    print("[chat-consumer] Application shutting down...")  # Runs on shutdown


# Create the FastAPI app with the lifespan event
app = FastAPI(lifespan=lifespan)
app.include_router(websocket_router)


@app.get("/")
def health():
    return {"status": "chat-consumer OK"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True, log_level="debug")
