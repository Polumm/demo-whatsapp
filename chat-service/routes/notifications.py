import httpx

async def send_push_notification(user_id: str, msg_data: dict):
    """
    Example push notification logic for offline user.
    In practice, you'd call a push service or FCM/APNs, etc.
    """
    print(f"[notifications] Sending push to {user_id}: {msg_data}")
    # Example mock call
    async with httpx.AsyncClient() as client:
        # Dummy push endpoint
        # (Or do something real for your environment)
        await client.post(
            "http://example-push-service/push",
            json={"user_id": user_id, "payload": msg_data},
        )
