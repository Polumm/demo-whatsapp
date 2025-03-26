import requests
import jwt
import datetime
import websocket

BASE_URL = "http://127.0.0.1:8000"


# Test Login (Server Determines Role)
def test_login(username, password):
    response = requests.post(
        f"{BASE_URL}/login",
        headers={"Content-Type": "application/json"},
        json={"username": username, "password": password},
    )
    print(f"Login ({username}):", response.status_code, response.json())
    return response.json().get("access_token")


# Test Accessing Protected Routes with JWT
def test_protected_route(endpoint, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)

    try:
        json_response = response.json()
    except requests.exceptions.JSONDecodeError:
        json_response = {
            "error": "Invalid JSON response",
            "text": response.text,
        }

    print(f"Accessing {endpoint}: {response.status_code}, {json_response}")
    return response.status_code, json_response


# Test WebSocket Connection with JWT
def test_websocket(token=None):
    ws_url = f"ws://127.0.0.1:8000/ws"

    try:
        if token:
            ws = websocket.WebSocket()
            ws.connect(ws_url, header={"Sec-WebSocket-Protocol": token})
            print("✅ WebSocket connected successfully!")
            ws.send("Hello Server!")
            response = ws.recv()
            print(f"🔁 WebSocket Response: {response}")
            ws.close()
        else:
            ws = websocket.WebSocket()
            ws.connect(ws_url)
            print("❌ WebSocket should not connect without a token!")
    except Exception as e:
        print(f"🚨 WebSocket connection failed: {e}")


# Test Unauthorized Access (No Login)
print("\n🛑 Test 1: Trying to Access Protected APIs Without Logging In")
test_protected_route("/admin")  # Should return 401 Unauthorized
test_protected_route("/user")  # Should return 401 Unauthorized

# Test Unauthorized WebSocket Connection (Should Fail)
print("\n🛑 Test 2: Trying to Connect WebSocket Without Token")
test_websocket(None)  # Should fail

# Login Test
print("\n✅ Test 3: Login as Admin and User")
admin_token = test_login("admin_user", "adminpass")
user_token = test_login("normal_user", "userpass")

# Check if tokens were received
if not admin_token or not user_token:
    print("\n❌ Login failed. Exiting tests.")
    exit(1)

# Test Accessing Protected Routes with Valid JWT
print("\n🔐 Test 4: Accessing Protected Routes with Valid JWT")
test_protected_route("/admin", admin_token)  # ✅ Should work
test_protected_route("/user", admin_token)  # ✅ Should work
test_protected_route("/user", user_token)  # ✅ Should work
test_protected_route("/admin", user_token)  # ❌ Should return 403 Forbidden

# Test WebSocket Connection with Valid JWT
print("\n🔐 Test 5: Connecting WebSocket with Valid JWT")
test_websocket(admin_token)  # ✅ Should work
test_websocket(user_token)  # ✅ Should work

# Test Stolen Token
print("\n🚨 Test 6: Using Stolen Token (Admin Token as User)")
stolen_token = admin_token  # Simulating a stolen admin token
test_protected_route(
    "/user", stolen_token
)  # ✅ Should work (⚠️ Security risk if still works)
test_protected_route(
    "/admin", stolen_token
)  # ✅ Should work (⚠️ Security risk if still works)
test_websocket(stolen_token)  # ✅ Should work (⚠️ Security risk if still works)

# Test Expired Token
print("\n⏳ Test 7: Expired Token Simulation")
expired_token = jwt.encode(
    {
        "sub": "test_user",
        "role": "admin",
        "exp": datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(hours=1),
    },
    "access_secret_key",
    algorithm="HS256",
)
test_protected_route(
    "/admin", expired_token
)  # ❌ Should return 401 Token Expired
test_websocket(expired_token)  # ❌ Should fail to connect WebSocket
