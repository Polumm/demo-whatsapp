from fastapi import FastAPI
import uvicorn
import threading

from routes.websocket import router as websocket_router
from consumers.consumer import blocking_consume

app = FastAPI()
app.include_router(websocket_router)


@app.get("/")
def health():
    return {"status": "chat-consumer OK"}


@app.on_event("startup")
def startup_event():
    """
    Spawn a separate thread that runs the blocking consumer loop.
    This won't block the FastAPI main thread.
    """
    thread = threading.Thread(target=blocking_consume, daemon=True)
    thread.start()
    print("[chat-consumer] Background consumer thread started.")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
