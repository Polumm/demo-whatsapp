from fastapi import FastAPI
import uvicorn
import threading
import asyncio
from contextlib import asynccontextmanager

from routes.websocket import router as websocket_router
from consumers.consumer import blocking_consume, set_main_loop


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Replaces the deprecated @app.on_event("startup") approach.
    1) Acquire resources at startup
    2) Release them on shutdown
    """
    # 1) STARTUP
    # Capture the main event loop used by FastAPI
    loop = asyncio.get_running_loop()
    set_main_loop(loop)

    # Start the blocking RabbitMQ consumer in a separate thread
    thread = threading.Thread(target=blocking_consume, daemon=True)
    thread.start()
    print("[chat-service] Background consumer thread started.")

    # Yield control so the app can start serving requests
    yield

    # 2) SHUTDOWN
    print("[chat-service] Shutting down...")
    # (If you need to signal the consumer thread to stop, do that here.)
    # The thread will be killed when the process ends, or you can join it if you want.


# Create the app using the lifespan context manager
app = FastAPI(lifespan=lifespan)
app.include_router(websocket_router)


@app.get("/")
def health_check():
    return {"status": "chat-service OK"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
