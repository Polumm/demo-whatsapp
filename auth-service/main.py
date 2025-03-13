import uvicorn
from fastapi import FastAPI, Request
from routes.login import router as login_router
from routes.register import router as register_router
from sqlalchemy import create_engine
from config import DATABASE_URL, APP_ENV
from models import Base
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Auto-create tables in development mode
if APP_ENV == "development":
    print("Running in development mode: Creating tables...")
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)


# Middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    logger.info(
        f"🔵 Incoming request: {request.method} {request.url} | Body: {body.decode()}"
    )
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response


app.include_router(login_router)
app.include_router(register_router)


@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "auth-service OK"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
