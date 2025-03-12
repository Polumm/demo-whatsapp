from fastapi import FastAPI
import uvicorn
from routes.websocket import router as websocket_router

app = FastAPI()
app.include_router(websocket_router)


@app.get("/")
async def health_check():
    """Health check endpoint to confirm service is running."""
    return {"status": "chat-publisher OK"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
