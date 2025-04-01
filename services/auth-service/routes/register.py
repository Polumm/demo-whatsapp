from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from dependencies import get_db
from models import User
from routes.security import hash_password
import uuid

router = APIRouter()

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str

@router.post("/register")
async def register_user(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new user in the database."""
    # Check if user exists
    result = await db.execute(select(User).where(User.name == data.username))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user
    new_user = User(
        id=uuid.uuid4(),
        name=data.username,
        password=hash_password(data.password),
        role=data.role,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "user_id": str(new_user.id),
        "created_at": new_user.created_at,
    }
