import jwt
import pika
import json
from functools import wraps
from config import (
    ACCESS_SECRET_KEY,
    ALGORITHM,
)
from fastapi import Request, WebSocket, HTTPException
from typing import Optional, Union
import httpx


shared_httpx_client = httpx.AsyncClient(timeout=10)

async def get_http_client() -> httpx.AsyncClient:
    return shared_httpx_client


def _extract_jwt(
    request: Optional[Request] = None, websocket: Optional[WebSocket] = None
):
    """
    Extract JWT token from:
      - HTTP: request.headers["Authorization"]
      - WebSocket: websocket.headers["sec-websocket-protocol"]
    """
    token = None

    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
    elif websocket:
        token = websocket.headers.get("sec-websocket-protocol")
        
    if not token:
        raise HTTPException(
            status_code=401, detail="Authorization token missing or invalid"
        )
    return token


def verify_token(token: str):
    """
    Decodes and verifies JWT token.
    """
    try:
        return jwt.decode(token, ACCESS_SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise Exception(
            "Token has expired"
        )  # Change from HTTPException to general Exception
    except jwt.InvalidTokenError:
        raise Exception(
            "Invalid token"
        )  # Change from HTTPException to general Exception


def role_required(*allowed_roles):
    def decorator(endpoint_func):
        @wraps(endpoint_func)
        async def wrapper(*args, **kwargs):
            request = None
            websocket = None

            # Figure out if we have a Request or WebSocket in args/kwargs
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, WebSocket):
                    websocket = arg

            if 'request' in kwargs and isinstance(kwargs['request'], Request):
                request = kwargs['request']
            if 'websocket' in kwargs and isinstance(kwargs['websocket'], WebSocket):
                websocket = kwargs['websocket']

            try:
                token = _extract_jwt(request, websocket)
                decoded_token = verify_token(token)
                user_role = decoded_token.get("role")

                if not user_role or user_role not in allowed_roles:
                    raise HTTPException(status_code=403, detail="Insufficient role")

                # Attach token info and continue
                if request is not None:
                    request.state.token_data = decoded_token
                if websocket is not None:
                    websocket.state.token_data = decoded_token

                return await endpoint_func(*args, **kwargs)

            except Exception as e:
                if websocket:
                    await websocket.close(code=1008)
                    return
                else:
                    # For HTTP calls, raise HTTP 401
                    raise HTTPException(status_code=401, detail=str(e))

        return wrapper
    return decorator


def self_user_only(user_id_param: str = "user_id"):
    """
    Verifies that the user_id in the path/query matches the JWT subject (sub),
    supports both HTTP request and WebSocket.
    """
    def decorator(endpoint_func):
        @wraps(endpoint_func)
        async def wrapper(*args, **kwargs):
            request_or_ws: Optional[Union[Request, WebSocket]] = None

            # Detect whether it's a Request or WebSocket
            for arg in args:
                if isinstance(arg, (Request, WebSocket)):
                    request_or_ws = arg

            if 'request' in kwargs and isinstance(kwargs['request'], Request):
                request_or_ws = kwargs['request']
            elif 'websocket' in kwargs and isinstance(kwargs['websocket'], WebSocket):
                request_or_ws = kwargs['websocket']

            if not request_or_ws:
                raise HTTPException(500, "Request or WebSocket object missing")

            # Extract token data
            token_data = getattr(request_or_ws.state, "token_data", None)
            if not token_data:
                raise HTTPException(401, "Unauthorized")

            user_id_from_token = token_data.get("sub")
            user_id_from_query = kwargs.get(user_id_param)

            if str(user_id_from_token) != str(user_id_from_query):
                raise HTTPException(403, f"Forbidden: Not your data \n"
                                         f"user_id_from_token: {user_id_from_token} \n"
                                         f"user_id_from_query: {user_id_from_query}")

            return await endpoint_func(*args, **kwargs)
        return wrapper
    return decorator
