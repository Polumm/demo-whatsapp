from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from config import AUTH_SERVICE_URL
from dependencies import get_http_client
import httpx

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str


@router.post("/login")
async def login(request: LoginRequest, client: httpx.AsyncClient = Depends(get_http_client)):
    try:
        response = await client.post(f"http://{AUTH_SERVICE_URL}/login", json=request.model_dump())
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=401, detail="Authentication failed")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Auth service error: {str(e)}")


@router.post("/register")
async def register(request: RegisterRequest, client: httpx.AsyncClient = Depends(get_http_client)):
    try:
        response = await client.post(f"http://{AUTH_SERVICE_URL}/register", json=request.model_dump())
        if response.status_code == 200:
            return response.json()
        raise HTTPException(status_code=400, detail="Registration failed")
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Auth service error: {str(e)}")
