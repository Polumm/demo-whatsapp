# 🧪 Demo WhatsApp Gateway - Testing Guide 

This guide covers how to test the Gateway service and downstream Chat APIs using both:

- ✅ Raw tools like `curl` and `wscat`
- ✅ The official `demo_client.py` CLI

---

## 📦 Prerequisites

- Python 3.9+ with `venv` activated
- Installed dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- `wscat` installed globally:
  ```bash
  npm install -g wscat
  ```

---

## 🚀 1. Login (Get JWT)

```bash
curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Alice", "password": "Alice", "role": "user"}'

curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Bob", "password": "Bob", "role": "user"}'
```

Copy the `access_token` from each response.

---

## 🌐 2. WebSocket Testing with `wscat`

Now supports `device_id` via query parameter:

```bash
wscat -c "ws://localhost:8001/api/ws/<user_id>?device_id=<device_id>" \
  -H "sec-websocket-protocol: <access_token>"
```

### Example:

```bash
wscat -c "ws://localhost:8001/api/ws/22e73da1-...Alice?device_id=dev-alice-laptop" \
  -H "sec-websocket-protocol: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

> 🟡 Do **NOT** include `"Bearer "` prefix in WebSocket headers!

---

## 🔄 3. Sync Messages (GET `/sync`)

```bash
curl -X GET "http://localhost:8001/api/sync?user_id=<user_id>&since=<unix_timestamp>" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json"
```

To get a timestamp:

```bash
date -d '10 minutes ago' +%s
```

---

## 💬 4. Create a Conversation

```bash
curl -X POST http://localhost:8001/api/conversations \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "direct",
    "name": "Alice-Bob-Chat",
    "user_ids": [
      "22e73da1-...Alice",
      "fa23d151-...Bob"
    ]
  }'
```

---

## 💻 5. Use `demo_client.py` CLI (Recommended)

### ✅ Login

```bash
python tests/demo_client.py login --username Alice --password Alice
python tests/demo_client.py login --username Bob --password Bob
```

### ✅ Connect via WebSocket

```bash
python tests/demo_client.py ws \
  --user Alice \
  --user-id 22e73da1-... \
  --device-id dev-alice-laptop

python tests/demo_client.py ws \
  --user Bob \
  --user-id fa23d151-... \
  --device-id dev-bob-phone
```

> If `--device-id` is not provided, a random one is generated.

### ✅ Sync Messages

```bash
# Using relative time
python tests/demo_client.py call \
  --user Alice \
  --endpoint "sync?user_id=22e73da1-..." \
  --since "10 minutes ago"

# Using raw timestamp
python tests/demo_client.py call \
  --user Alice \
  --endpoint "sync?user_id=22e73da1-..." \
  --since "1743507237.889304"
```

### ✅ Create Conversation via CLI

```bash
python tests/demo_client.py call \
  --user Alice \
  --endpoint "conversations" \
  --method post \
  --body '{"type": "direct", "name": "Alice-Bob-Chat", "user_ids": ["22e73da1-...", "fa23d151-..."]}'
```

---

## 🧠 Notes

- WebSocket JWTs must be passed via the `sec-websocket-protocol` header (raw token, no `Bearer`).
- HTTP JWTs use the `Authorization: Bearer <token>` header.
- WebSocket connections **must include `device_id`**.
- Timestamps must be UNIX-style (`int` or `float`). Use `"10 minutes ago"` with `demo_client.py`.

---

## 📂 Files of Interest

| File                            | Purpose                                |
|----------------------------------|----------------------------------------|
| `tests/demo_client.py`         | Custom CLI for login, sync, WebSocket  |
| `tests/tmp/.tokens.json`       | Stores JWTs locally                    |
| `services/gateway-service/...` | FastAPI decorators + JWT verification  |
```