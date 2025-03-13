from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.security import HTTPBearer
from pydantic import BaseModel
import jwt
import datetime
from functools import wraps
import uvicorn

app = FastAPI()

# Secret keys for encoding/decoding JWT
ACCESS_SECRET_KEY = "access_secret_key"
ALGORITHM = "HS256"

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# Simulated database: username -> {"password": str, "role": str}
FAKE_DB = {
    "admin_user": {"password": "adminpass", "role": "admin"},
    "normal_user": {"password": "userpass", "role": "user"},
}

# Token authentication scheme
security = HTTPBearer()


class LoginRequest(BaseModel):
    username: str
    password: str


def create_token(
    user_id: str, role: str, secret_key: str, expires_delta: datetime.timedelta
):
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + expires_delta,
    }
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def generate_tokens(user_id: str, role: str):
    access_token = create_token(
        user_id,
        role,
        ACCESS_SECRET_KEY,
        datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": access_token}


def _extract_jwt(request: Request = None, websocket: WebSocket = None):
    """
    Extract token from either:
      - request.headers["Authorization"]  (HTTP)
      - websocket.headers["sec-websocket-protocol"] (WebSocket)
    """
    token = None
    if request is not None:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    elif websocket is not None:
        token = websocket.headers.get("sec-websocket-protocol")

    if not token:
        raise HTTPException(
            status_code=401, detail="Authorization token missing or invalid"
        )
    return token


def verify_token(token: str, secret_key: str):
    try:
        decoded_token = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def role_required(*allowed_roles):
    """
    Decorator to enforce role-based authentication for both HTTP and WebSocket endpoints.
    Stores the decoded token in request.state.token_data or websocket.state.token_data.
    """

    def decorator(endpoint_func):
        @wraps(endpoint_func)
        async def wrapper(
            *args,
            request: Request = None,
            websocket: WebSocket = None,
            **kwargs,
        ):
            token = _extract_jwt(request, websocket)
            decoded_token = verify_token(token, ACCESS_SECRET_KEY)

            user_role = decoded_token.get("role")
            if not user_role:
                raise HTTPException(
                    status_code=401, detail="Invalid token payload"
                )

            if user_role not in allowed_roles:
                raise HTTPException(
                    status_code=403, detail="Insufficient role"
                )

            # Attach decoded token to request or websocket, so the endpoint can retrieve it.
            if request is not None:
                request.state.token_data = decoded_token
                return await endpoint_func(request=request, *args, **kwargs)
            else:
                websocket.state.token_data = decoded_token
                return await endpoint_func(
                    websocket=websocket, *args, **kwargs
                )

        return wrapper

    return decorator


@app.post("/login")
async def login(data: LoginRequest):
    user = FAKE_DB.get(data.username)
    if not user or user["password"] != data.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    role = user["role"]
    tokens = generate_tokens(data.username, role)
    return tokens


# ---------------------------
# Protected Endpoints
# ---------------------------


@app.websocket("/ws")
@role_required("admin", "user")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint requiring 'admin' or 'user' role.
    Decoded token is available at websocket.state.token_data.
    """
    token_data = websocket.state.token_data
    user_id = token_data["sub"]
    user_role = token_data["role"]

    # No subprotocol negotiation, just accept the socket
    await websocket.accept()
    await websocket.send_text(
        f"Welcome {user_id}! You have {user_role} access."
    )
    try:
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"Echo: {msg}")
    except WebSocketDisconnect:
        print(f"User {user_id} disconnected")


@app.get("/admin")
@role_required("admin")
async def admin_endpoint(request: Request):
    """
    HTTP endpoint requiring 'admin' role.
    Decoded token is available at request.state.token_data.
    """
    token_data = request.state.token_data
    user_id = token_data["sub"]
    return {
        "message": f"Hello, Admin (user_id={user_id})! You have admin access."
    }


@app.get("/user")
@role_required("admin", "user")
async def user_endpoint(request: Request):
    """
    HTTP endpoint accessible to 'admin' or 'user'.
    Decoded token is available at request.state.token_data.
    """
    token_data = request.state.token_data
    user_id = token_data["sub"]
    return {"message": f"Hello, {user_id}! You have user access."}


# Public, no auth required
@app.get("/")
async def public_endpoint():
    return {"message": "Welcome to the public API!"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


# uvicorn tests.demo-jwt:app --host 127.0.0.1 --port 8000 --reload
