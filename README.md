# demo-whatsapp

A scalable, real-time messaging system supporting multi-device delivery, group chats, presence-based routing, and guaranteed message delivery across distributed nodes. Built with **FastAPI**, **RabbitMQ**, **Redis**, and **PostgreSQL**.

---

## 📚 Table of Contents

- [demo-whatsapp](#demo-whatsapp)
  - [📚 Table of Contents](#-table-of-contents)
  - [🟦 Chat-Service Overview](#-chat-service-overview)
    - [🧩 Design Overview](#-design-overview)
  - [✨ Key Features](#-key-features)
  - [🔧 Technical Highlights](#-technical-highlights)
  - [📦 System Flow Example](#-system-flow-example)
  - [🧪 Demo WhatsApp Gateway - Testing Guide](#-demo-whatsapp-gateway---testing-guide)
    - [📦 Prerequisites](#-prerequisites)
    - [🚀 1. Login (Get JWT)](#-1-login-get-jwt)
    - [🌐 2. WebSocket Testing with `wscat`](#-2-websocket-testing-with-wscat)
    - [🔄 3. Sync Messages (GET `/sync`)](#-3-sync-messages-get-sync)
    - [💬 4. Create a Conversation](#-4-create-a-conversation)
    - [💻 5. Use `demo_client.py` CLI (Recommended)](#-5-use-demo_clientpy-cli-recommended)
    - [🧠 Notes](#-notes)
    - [📂 Files of Interest](#-files-of-interest)
  - [🧱 Microservice Structure](#-microservice-structure)
    - [🧩 Core Services](#-core-services)
    - [🧪 Infrastructure](#-infrastructure)

---

## 🟦 Chat-Service Overview

The **chat-service** is the core real-time messaging component responsible for delivering messages between users across multiple devices and distributed server nodes. It supports:

- **1-on-1 chat**
- **Group messaging**
- **Self-syncing** across a user’s devices

It guarantees high delivery reliability, horizontal scalability, and modular extensibility through a well-structured architecture built on FastAPI and RabbitMQ.

### 🧩 Design Overview

At the heart of the chat-service is a **producer–persistor–consumer** pattern that handles message lifecycle across distributed systems:

- **Producer:**  
  Accepts inbound messages from WebSocket connections, determines the recipient devices (via presence-service), and publishes node-level messages to RabbitMQ using routing keys based on `node_id`.

- **Persistor:**  
  Each message is simultaneously published to a separate persistence exchange. A dedicated `persistence-service` listens for these messages and stores them in both Redis (for fast access) and PostgreSQL (for durability).

- **Consumer:**  
  Each chat-service node runs a consumer that listens to its own RabbitMQ queue (bound by its `NODE_ID`). It receives only messages relevant to its devices and forwards them to connected WebSocket clients.

This design enables **low-latency delivery**, **node-local dispatching**, and **reliable storage**, while ensuring **horizontal scalability**.

---

## ✨ Key Features

- **Multi-device Delivery**  
  Messages are delivered to all active devices for a user (excluding the sender's originating device).

- **Scalable Node Architecture**  
  Messages are routed via RabbitMQ across multiple chat-service nodes.

- **Fully Asynchronous Endpoints**  
  Non-blocking I/O for HTTP and WebSocket APIs using `async`/`await`.

- **Real-time WebSocket Layer**  
  Persistent WebSocket connections enable bi-directional, low-latency communication.

- **Unified Message Flow**  
  ```text
  client → user-level → device-level → node-level → device-level → client
  ```

- **Presence-Aware Routing**  
  Integrates with the `presence-service` to ensure messages are only sent to online devices.

- **Bulk Optimized Routing**  
  Groups devices by `node_id` using a batch lookup to reduce routing overhead.

- **Guaranteed Delivery Semantics**  
  - At-least-once delivery at the node level  
  - Optional device-level deduplication and acknowledgment tracking

---

## 🔧 Technical Highlights

- **FastAPI** – WebSocket and HTTP routing framework
- **aio-pika / RabbitMQ** – Async message fan-out with durable queues
- **Redis + PostgreSQL** – High-performance cache and persistent message storage
- **Presence-Service Integration** – Ensures message delivery is device-aware
- **Modular Microservices** – Each responsibility (gateway, persistence, presence, auth) is separated

---

## 📦 System Flow Example

1. Client sends a message via WebSocket to `chat-service`
2. The message is:
   - Persisted for durability (via `persistor` to Redis/PostgreSQL)
   - Routed using `presence-service` to identify online devices
   - Grouped by node and published to RabbitMQ
3. Each node's `consumer` delivers messages to WebSocket clients connected on that node only

> ⬇️ **Relevant Code Files** (under `services/chat-service/message_transport/`):
>
> - `producer.py`: Publishes node-bound messages and handles presence routing  
> - `persistor.py`: Publishes messages to the persistence queue  
> - `consumer.py`: Listens to the node's queue and delivers to local devices  
> - `persistence-service/persistence.py`: Consumes persisted messages and stores in Redis + Postgres

---

## 🧪 Demo WhatsApp Gateway - Testing Guide

This section describes how to test the Gateway service and downstream Chat APIs using both raw HTTP/WebSocket and a CLI tool.

---

### 📦 Prerequisites

- Docker installed
- Build the project:

```bash
./build
cd tests
```

---

### 🚀 1. Login (Get JWT)

```bash
curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Alice", "password": "Alice", "role": "user"}'

curl -X POST http://localhost:8001/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "Bob", "password": "Bob", "role": "user"}'
```

---

### 🌐 2. WebSocket Testing with `wscat`

```bash
wscat -c "ws://localhost:8001/api/ws/<user_id>?device_id=<device_id>" \
  -H "sec-websocket-protocol: <access_token>"
```

**Example:**
```bash
wscat -c "ws://localhost:8001/api/ws/22e73da1-Alice?device_id=dev-alice-laptop" \
  -H "sec-websocket-protocol: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

> ⚠️ **Important:** Do **NOT** include the `"Bearer "` prefix in WebSocket headers!

---

### 🔄 3. Sync Messages (GET `/sync`)

```bash
curl -X GET "http://localhost:8001/api/sync?user_id=<user_id>&since=<unix_timestamp>" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json"
```

Get a timestamp:

```bash
date -d '10 minutes ago' +%s
```

---

### 💬 4. Create a Conversation

```bash
curl -X POST http://localhost:8001/api/conversations \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "direct",
    "name": "Alice-Bob-Chat",
    "user_ids": [
      "22e73da1-Alice",
      "fa23d151-Bob"
    ]
  }'
```

---

### 💻 5. Use `demo_client.py` CLI (Recommended)

✅ Login:

```bash
python tests/demo_client.py login --username Alice --password Alice
python tests/demo_client.py login --username Bob --password Bob
```

✅ Connect via WebSocket:

```bash
python tests/demo_client.py ws --user Alice --user-id 22e73da1-Alice --device-id dev-alice-laptop
python tests/demo_client.py ws --user Bob --user-id fa23d151-Bob --device-id dev-bob-phone
```

✅ Sync Messages:

```bash
python tests/demo_client.py call \
  --user Alice \
  --endpoint "sync?user_id=22e73da1-Alice" \
  --since "10 minutes ago"
```

✅ Create Conversation via CLI:

```bash
python tests/demo_client.py call \
  --user Alice \
  --endpoint "conversations" \
  --method post \
  --body '{"type": "direct", "name": "Alice-Bob-Chat", "user_ids": ["22e73da1-Alice", "fa23d151-Bob"]}'
```

---

### 🧠 Notes

- WebSocket JWTs **must** be passed via `sec-websocket-protocol` as the **raw token**.
- HTTP requests use `Authorization: Bearer <token>`.
- All WebSocket connections **must** include a `device_id` query parameter.
- Timestamps should be UNIX-style integers or floats. The CLI accepts relative phrases like `"10 minutes ago"`.

---

### 📂 Files of Interest

| File                         | Description                               |
|------------------------------|-------------------------------------------|
| `tests/demo_client.py`       | CLI tool for login, message sync, and WS  |
| `tests/tmp/.tokens.json`     | Stores local JWT tokens                   |
| `services/gateway-service/`  | FastAPI service with JWT auth + WS proxy  |

---

## 🧱 Microservice Structure

### 🧩 Core Services

| Service             | Description                                  |
|---------------------|----------------------------------------------|
| `chat-service`      | Real-time WebSocket and message routing      |
| `gateway-service`   | API gateway with JWT authentication          |
| `presence-service`  | Tracks online devices using Redis            |
| `persistence-service` | Persists messages to Redis and PostgreSQL |

### 🧪 Infrastructure

- **RabbitMQ** – Message broker between distributed nodes
- **Redis** – Fast in-memory cache and presence tracking
- **PostgreSQL** – Persistent database for messages and auth
- **HAProxy** – Load balancer for chat-service replicas

---
