import jwt
import datetime
import bcrypt
from config import ACCESS_SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


def create_token(user_id, role: str):
    """Generates a JWT token"""
    payload = {
        "sub": str(user_id),  # Convert UUID to string
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=int(ACCESS_TOKEN_EXPIRE_MINUTES)),
    }
    return jwt.encode(payload, ACCESS_SECRET_KEY, algorithm=ALGORITHM)


def generate_tokens(user_id: str, role: str):
    """Generates access tokens"""
    access_token = create_token(user_id, role)

    return {"access_token": access_token, "token_type": "bearer"}


def hash_password(password: str) -> str:
    """Hashes the password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against its hash"""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
