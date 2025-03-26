import os
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from dependencies import Base, engine
from routers import presence

# Environment variable to determine development mode
APP_ENV = os.getenv("APP_ENV", "development")

def create_tables():
    """Creates database tables only in development mode (avoid in production)."""
    if APP_ENV == "development":
        print("[presence-service] Running in development mode: Creating tables...")
        Base.metadata.create_all(bind=engine)


# New lifespan function
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[presence-service] Creating tables if not exist...")
    create_tables()
    yield  # Application runs here
    print("[presence-service] Shutting down presence-service...")  # Cleanup if needed

# Use the lifespan parameter in FastAPI
app = FastAPI(lifespan=lifespan)

# Include routes
app.include_router(presence.router, prefix="/presence")

@app.get("/")
def health_check():
    return {"status": "presence-service OK"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=True)
