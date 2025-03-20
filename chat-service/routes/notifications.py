import asyncio


async def send_push_notification(user_id, msg_data):
    """
    Mock push notification for offline users.
    """
    await asyncio.sleep(0.01)  # simulate I/O
    print(f"[chat-consumer] (Mock) push notification to {user_id}: {msg_data}")