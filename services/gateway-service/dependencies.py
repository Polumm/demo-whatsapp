import jwt
import pika
import json
from functools import wraps
from config import (
    ACCESS_SECRET_KEY,
    ALGORITHM,
)
from fastapi import Request, WebSocket, HTTPException
from typing import Optional
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
        protocol_header = websocket.headers.get("sec-websocket-protocol")
        if protocol_header and protocol_header.startswith("Bearer "):
            token = protocol_header.split(" ")[1]

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
    Verifies that the user_id in the request path or query matches the JWT.
    """
    def decorator(endpoint_func):
        @wraps(endpoint_func)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = None

            # 1) Figure out which arg is the request
            for arg in args:
                if isinstance(arg, Request):
                    request = arg

            if 'request' in kwargs and isinstance(kwargs['request'], Request):
                request = kwargs['request']

            if not request:
                raise HTTPException(500, "Request object missing")

            # 2) Pull token_data from request.state
            token_data = getattr(request.state, "token_data", None)
            if not token_data:
                raise HTTPException(401, "Unauthorized")

            # 3) Compare user ID
            user_id_from_token = token_data.get("user_id")
            # If your path param is "user_id" in your route, then it’s probably in kwargs:
            user_id_from_query = kwargs.get(user_id_param)

            if str(user_id_from_token) != str(user_id_from_query):
                raise HTTPException(403, "Forbidden: Not your data")

            return await endpoint_func(*args, **kwargs)
        return wrapper
    return decorator
