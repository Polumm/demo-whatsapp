from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from routes.security import generate_tokens, verify_password
from dependencies import get_db
from sqlalchemy.orm import Session
from models import User

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Validates user credentials against the database & returns JWT token."""
    user = db.query(User).filter(User.name == data.username).first()

    if not user or not verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    tokens = generate_tokens(user.id, user.role)
    return tokens
