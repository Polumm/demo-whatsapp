from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from dependencies import shared_httpx_client

from routes.auth import router as auth_router
from routes.chat import router as chat_ws_router
from routes.conversation import router as convo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[gateway] Starting up...")
    yield
    print("[gateway] Shutting down...")
    await shared_httpx_client.aclose()


app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(chat_ws_router, prefix="/api")
app.include_router(convo_router, prefix="/api")


@app.get("/")
async def health_check():
    return {"status": "gateway-service OK"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="debug")
