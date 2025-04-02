import httpx
import logging

async def send_push_notification(user_id: str, msg_data: dict):
    """
    Send a push notification to an external service for an offline user.
    Handles timeouts and logs the result safely.
    """
    logging.info(f"[notifications] Sending push to {user_id}: {msg_data}")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://example-push-service/push",  # Replace with your actual push endpoint
                json={"user_id": user_id, "payload": msg_data},
            )
            response.raise_for_status()
            logging.info(f"[notifications] Push sent to {user_id} (status={response.status_code})")

    except httpx.ConnectTimeout:
        logging.warning(f"[notifications] Timeout trying to reach push service for {user_id}")
    except httpx.HTTPStatusError as e:
        logging.error(f"[notifications] HTTP error for {user_id}: {e.response.status_code} {e.response.text}")
    except httpx.RequestError as e:
        logging.error(f"[notifications] Request error for {user_id}: {str(e)}")
    except Exception as e:
        logging.exception(f"[notifications] Unexpected error sending push to {user_id}: {e}")
