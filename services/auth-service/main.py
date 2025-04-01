import logging
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from routes.login import router as login_router
from routes.register import router as register_router
from config import APP_ENV
from models import Base
from dependencies import engine

# --- Lifespan Setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if APP_ENV == "development":
        print("[auth-service] Running in development mode: Creating tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[auth-service] Tables created.")
    yield
    # optional: cleanup here if needed
    print("[auth-service] Lifespan shutdown: cleanup complete")

# --- FastAPI App ---
app = FastAPI(lifespan=lifespan)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url} | Headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# --- Routers ---
app.include_router(login_router)
app.include_router(register_router)

@app.get("/")
async def health_check():
    return {"status": "auth-service OK"}

# --- Dev Entry Point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
