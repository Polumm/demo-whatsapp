import jwt
import pika
import json
from functools import wraps
from config import (
    RABBIT_HOST,
    RABBIT_PORT,
    QUEUE_NAME,
    ACCESS_SECRET_KEY,
    ALGORITHM,
)
from fastapi import Request, WebSocket, HTTPException
from typing import Optional


def publish_message(message_dict):
    """Publishes a message to RabbitMQ."""
    try:
        with pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBIT_HOST, port=RABBIT_PORT)
        ) as connection:
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)

            # message_dict is a dict => we do a single json.dumps here
            channel.basic_publish(
                exchange="",
                routing_key=QUEUE_NAME,
                body=json.dumps(message_dict).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),  # persistent
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error publishing message: {e}"
        )


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
