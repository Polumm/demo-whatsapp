import os
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager

from routers import presence

APP_ENV = os.getenv("APP_ENV", "development")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[presence-service] Starting up (Redis only, no DB creation needed)...")
    yield
    print("[presence-service] Shutting down presence-service...")

app = FastAPI(lifespan=lifespan)

# Include presence routes
app.include_router(presence.router, prefix="/presence")

@app.get("/")
async def health_check():
    return {"status": "presence-service OK"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
