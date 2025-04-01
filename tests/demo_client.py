import typer
import requests
import json
import asyncio
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from pathlib import Path
from rich import print
from datetime import datetime
import dateutil.parser
import dateutil.relativedelta
from dateutil import tz
import re

app = typer.Typer()

# Configuration
BASE_URL = "http://localhost:8001/api"
TOKEN_STORE = Path("tests/tmp/.tokens.json")
TOKEN_STORE.parent.mkdir(parents=True, exist_ok=True)

# -------------------------
# Helpers
# -------------------------
def parse_relative_time(value: str) -> int:
    """
    Accepts either a relative time string like '10 minutes ago'
    or a raw UNIX timestamp string like '1743507214.323039'.
    Returns an integer UNIX timestamp.
    """
    value = value.strip().lower()

    # If it's a float or int timestamp, return as int
    try:
        return int(float(value))
    except ValueError:
        pass

    # Try to match relative expressions like '10 minutes ago'
    match = re.match(r"(\d+)\s+(second|minute|hour|day)s?\s+ago", value)
    if not match:
        raise typer.BadParameter("Use a UNIX timestamp or a relative time like '10 minutes ago'")

    amount = int(match.group(1))
    unit = match.group(2)

    now = datetime.now(tz.UTC)
    delta = dateutil.relativedelta.relativedelta(**{unit + "s": amount})
    target_time = now - delta
    return int(target_time.timestamp())

def save_token(username: str, token: str):
    tokens = {}
    if TOKEN_STORE.exists():
        tokens = json.loads(TOKEN_STORE.read_text())
    tokens[username] = token
    TOKEN_STORE.write_text(json.dumps(tokens, indent=2))

def load_token(username: str) -> str:
    if not TOKEN_STORE.exists():
        raise typer.Exit("❌ Token store not found. Please login first.")
    tokens = json.loads(TOKEN_STORE.read_text())
    token = tokens.get(username)
    if not token:
        raise typer.Exit(f"❌ No token found for user '{username}'. Please login first.")
    return token

# -------------------------
# Commands
# -------------------------

@app.command()
def login(
    username: str = typer.Option(..., "--username", "-u", help="Username to log in"),
    password: str = typer.Option(..., "--password", "-p", help="Password for the user"),
    role: str = typer.Option("user", "--role", "-r", help="Role (default: user)")
):
    """Login and store JWT token."""
    resp = requests.post(f"{BASE_URL}/login", json={
        "username": username,
        "password": password,
        "role": role
    })
    if resp.ok:
        token = resp.json()["access_token"]
        save_token(username, token)
        print(f"[bold green]✅ Token saved for user: {username}[/bold green]")
    else:
        print(f"[bold red]❌ Login failed: {resp.status_code}[/bold red]")
        print(resp.text)

@app.command()
def call(
    user: str = typer.Option(..., "--user", "-u"),
    endpoint: str = typer.Option(..., "--endpoint", "-e"),
    method: str = typer.Option("get", "--method", "-m"),
    body: str = typer.Option(None, "--body"),
    since: str = typer.Option(None, "--since", help="Time filter like '10 minutes ago'")
):
    """Make an authenticated HTTP call to the API."""
    token = load_token(user)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    if since:
        timestamp = parse_relative_time(since)
        if "?" in endpoint:
            endpoint += f"&since={timestamp}"
        else:
            endpoint += f"?since={timestamp}"

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    response = requests.request(method.upper(), url, headers=headers, data=body)
    print(f"[cyan]➡️  {method.upper()} {url}[/cyan]")
    print(f"[bold yellow]Status: {response.status_code}[/bold yellow]")
    print(response.text)


@app.command()
def ws(
    user: str = typer.Option(..., "--user", "-u"),
    user_id: str = typer.Option(..., "--user-id"),
    device_id: str = typer.Option(None, "--device-id", "-d", help="Unique device ID (auto-generated if not provided)")
):
    """Connect to WebSocket using saved token and device ID."""

    import uuid
    if not device_id:
        device_id = f"dev-{uuid.uuid4().hex[:8]}"

    token = load_token(user)
    url = f"ws://localhost:8001/api/ws/{user_id}?device_id={device_id}"  # for gateway
    # If chat-service is called directly (not behind gateway):
    # url = f"ws://localhost:8002/ws/{user_id}/{device_id}"

    async def keepalive(ws):
        while True:
            try:
                await ws.ping()
                await asyncio.sleep(20)
            except Exception:
                break

    async def read_messages(ws):
        while True:
            try:
                msg = await ws.recv()
                print(f"[server] < {msg}")
            except ConnectionClosed:
                print("[red]🔌 Connection closed by server[/red]")
                break

    async def send_messages(ws):
        loop = asyncio.get_running_loop()
        while True:
            msg = await loop.run_in_executor(None, input, "[you] > ")
            await ws.send(msg)

    async def connect_ws():
        try:
            async with connect(url, subprotocols=[token]) as ws:
                print(f"[bold green]🟢 Connected as device {device_id}[/bold green]")
                receiver_task = asyncio.create_task(read_messages(ws))
                sender_task = asyncio.create_task(send_messages(ws))
                keepalive_task = asyncio.create_task(keepalive(ws))
                await asyncio.gather(receiver_task, sender_task, keepalive_task)
        except Exception as e:
            print(f"[bold red]❌ WebSocket error:[/bold red] {e}")

    asyncio.run(connect_ws())


if __name__ == "__main__":
    app()
