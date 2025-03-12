import websocket


def on_open(ws):
    print("WebSocket open")


def on_message(ws, msg):
    print("Received:", msg)


def on_close(ws, close_status, close_reason):
    print("Connection closed")


ws = websocket.WebSocketApp(
    "ws://localhost:8002/ws/Bob",
    on_open=on_open,
    on_message=on_message,
    on_close=on_close,
)
ws.run_forever()
