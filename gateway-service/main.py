from fastapi import FastAPI
import uvicorn

from routes.auth import router as auth_router
from routes.chat import router as chat_ws_router
from routes.conversation import router as convo_router

app = FastAPI()

# Include routers
app.include_router(auth_router, prefix="/api")
app.include_router(chat_ws_router, prefix="/api")
app.include_router(convo_router, prefix="/api")

@app.get("/")
async def health_check():
    """Health check endpoint to confirm service is running."""
    return {"status": "gateway-service OK"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="debug")
