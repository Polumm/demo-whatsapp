from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
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
def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    """Registers a new user in the database."""
    # Check if user exists
    existing_user = db.query(User).filter(User.name == data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create new user
    new_user = User(
        id=uuid.uuid4(),
        name=data.username,
        password=hash_password(data.password),
        role=data.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}
