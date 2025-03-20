import httpx
from config import PRESENCE_SERVICE_URL, NODE_ID

async def update_presence_status(user_id: str, status: str):
    """
    Calls the presence-service API (async) to update user status via httpx.
    """
    payload = {"user_id": user_id, "node_id": NODE_ID, "status": status}
    url = (
        f"{PRESENCE_SERVICE_URL}/presence/online"
        if status == "online"
        else f"{PRESENCE_SERVICE_URL}/presence/offline"
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                print(
                    f"[presence-service] Updated presence for {user_id} to {status} on {NODE_ID}"
                )
            else:
                print(
                    f"[presence-service] Failed to update presence for {user_id}: {response.text}"
                )
    except Exception as e:
        print(f"[presence-service] Error updating presence for {user_id}: {e}")
