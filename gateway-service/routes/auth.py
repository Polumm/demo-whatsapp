from fastapi import APIRouter, HTTPException
import requests
from pydantic import BaseModel
from config import AUTH_SERVICE_URL

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str


@router.post("/login")
def login(request: LoginRequest):
    """Forwards login request to auth-service and returns JWT token."""
    response = requests.post(f"{AUTH_SERVICE_URL}/login", json=request.model_dump())

    if response.status_code == 200:
        return response.json()  # Forward JWT token to frontend
    raise HTTPException(status_code=401, detail="Authentication failed")


@router.post("/register")
def register(request: RegisterRequest):
    """Forwards register request to auth-service and returns success message."""
    response = requests.post(
        f"{AUTH_SERVICE_URL}/register", json=request.model_dump()
    )

    if response.status_code == 200:
        return response.json()  # Forward success message to frontend
    raise HTTPException(status_code=400, detail="Registration failed")
