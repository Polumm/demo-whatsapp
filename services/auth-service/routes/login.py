from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from routes.security import generate_tokens, verify_password
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from dependencies import get_db
from models import User

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.name == data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return generate_tokens(user.id, user.role)
