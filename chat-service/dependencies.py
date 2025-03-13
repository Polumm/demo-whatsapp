import jwt
import pika
import redis
from functools import wraps
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    REDIS_HOST,
    REDIS_PORT,
    ACCESS_SECRET_KEY,
    ALGORITHM,
)
from fastapi import Request, WebSocket, HTTPException
from typing import Optional


# Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
)


def create_consumer_connection():
    """Creates a dedicated RabbitMQ connection for the consumer."""
    connection_params = pika.ConnectionParameters(
        host=RABBIT_HOST, port=RABBIT_PORT
    )
    return pika.BlockingConnection(connection_params)


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


import jwt
from functools import wraps
from fastapi import WebSocket
from typing import Optional


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
    """
    Decorator to enforce role-based authentication for both HTTP and WebSocket endpoints.
    """

    def decorator(endpoint_func):
        @wraps(endpoint_func)
        async def wrapper(
            *args,
            request: Optional[WebSocket] = None,
            websocket: Optional[WebSocket] = None,
            **kwargs,
        ):
            try:
                token = _extract_jwt(request, websocket)
                decoded_token = verify_token(token)
                user_role = decoded_token.get("role")

                if not user_role or user_role not in allowed_roles:
                    raise Exception("Insufficient role")

                # Attach decoded token to request or websocket
                if request:
                    request.state.token_data = decoded_token
                    return await endpoint_func(
                        request=request, *args, **kwargs
                    )
                elif websocket:
                    websocket.state.token_data = decoded_token
                    return await endpoint_func(
                        websocket=websocket, *args, **kwargs
                    )

            except Exception as e:  # Catch general exceptions
                if websocket:
                    await websocket.close(
                        code=1008
                    )  # Close WebSocket properly
                return  # Ensure the function exits without an error

        return wrapper

    return decorator
