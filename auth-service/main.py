import uvicorn
from fastapi import FastAPI, Request
from routes.login import router as login_router
from routes.register import router as register_router
from config import APP_ENV

from models import Base
from dependencies import engine  # Import existing engine from dependencies
import logging

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Auto-create tables only in development mode
if APP_ENV == "development":
    print("[auth-service] Running in development mode: Creating tables...")
    Base.metadata.create_all(bind=engine)

# Logging Middleware (Avoid reading full request body)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url} | Headers: {request.headers}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response

# Include routers
app.include_router(login_router)
app.include_router(register_router)

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "auth-service OK"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
