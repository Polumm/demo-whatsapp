import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from consumers.consumer import mq_to_client, set_main_loop
from main import app as websocket_app

client = TestClient(websocket_app)


@pytest.fixture
def unify_event_loop(event_loop):
    """
    Use the function-scoped event_loop from pytest-asyncio.
    Set MAIN_LOOP to this event_loop so that
    run_coroutine_threadsafe(...) uses the same loop
    that the test is awaiting on.
    """
    set_main_loop(event_loop)
    yield
    # no loop.close() or stop()


@pytest.mark.asyncio
async def test_mq_to_client(unify_event_loop):
    msg_data = {
        "conversation_id": "abc123",
        "toUser": "Bob",
        "sender_id": "Alice",
        "content": "Hello Bob!",
        "type": "text",
        "sent_at": 1710433845,
    }
    body = json.dumps(msg_data).encode()

    ch_mock = MagicMock()
    ch_mock.basic_ack = MagicMock()
    method_mock = MagicMock()
    method_mock.delivery_tag = 123

    ws_mock = AsyncMock()
    connected_users_mock = {"Bob": ws_mock}

    with (
        patch("consumers.consumer.connected_users", connected_users_mock),
        patch(
            "consumers.consumer.store_message_in_redis", new_callable=AsyncMock
        ) as mock_redis,
        patch(
            "consumers.consumer.store_message_in_postgres",
            new_callable=AsyncMock,
        ) as mock_postgres,
        patch(
            "consumers.consumer.send_push_notification", new_callable=AsyncMock
        ) as mock_push,
    ):
        # call
        mq_to_client(ch_mock, method_mock, None, body)
        # let tasks run
        await asyncio.sleep(0.1)

        ch_mock.basic_ack.assert_called_once()
        ws_mock.send_text.assert_awaited_once_with(json.dumps(msg_data))
        mock_redis.assert_awaited_once_with(msg_data)
        mock_postgres.assert_awaited_once_with(msg_data)
        mock_push.assert_not_awaited()


# @pytest.mark.asyncio
# async def test_group_chat_message(unify_event_loop):
#     """
#     group scenario => no toUser => get_group_members => Bob, Charlie online, Dave offline
#     """
#     msg_data = {
#         "conversation_id": "group_456",
#         "sender_id": "Alice",
#         "content": "Hey group!",
#         "type": "text",
#         "sent_at": 1710433845,
#     }
#     body = json.dumps(msg_data).encode()

#     ch_mock = MagicMock()
#     ch_mock.basic_ack = MagicMock()
#     method_mock = MagicMock()
#     method_mock.delivery_tag = 456

#     ws_bob = AsyncMock()
#     ws_charlie = AsyncMock()
#     connected_users_mock = {"Bob": ws_bob, "Charlie": ws_charlie}

#     with patch("consumers.consumer.connected_users", connected_users_mock), \
#          patch("consumers.consumer.get_group_members", return_value=["Bob","Charlie","Dave"]), \
#          patch("consumers.consumer.store_message_in_redis", new_callable=AsyncMock) as mock_redis, \
#          patch("consumers.consumer.store_message_in_postgres", new_callable=AsyncMock) as mock_postgres, \
#          patch("consumers.consumer.send_push_notification", new_callable=AsyncMock) as mock_push:

#         mq_to_client(ch_mock, method_mock, None, body)
#         await asyncio.sleep(0.1)

#         ch_mock.basic_ack.assert_called_once()
#         ws_bob.send_text.assert_awaited_once_with(json.dumps(msg_data))
#         ws_charlie.send_text.assert_awaited_once_with(json.dumps(msg_data))
#         mock_push.assert_awaited_once_with("Dave", msg_data)
#         mock_redis.assert_awaited_once_with(msg_data)
#         mock_postgres.assert_awaited_once_with(msg_data)


@pytest.mark.asyncio
async def test_websocket_message(unify_event_loop):
    """
    If your code calls publish_message(...) in a thread pool,
    we do .assert_called_once(), not .assert_awaited_once().
    Also patch the correct path. If it's in "chat_service.routes.websocket",
    do that. If it's "routes.websocket", do that.
    """
    with patch("routes.websocket.publish_message") as mock_publish:
        with client.websocket_connect("/ws/Alice") as ws:
            msg = {
                "conversation_id": "abc123",
                "to_user": "Bob",
                "content": "Hello Bob!",
            }
            ws.send_text(json.dumps(msg))

            # let any final tasks run
            await asyncio.sleep(0.1)

            mock_publish.assert_called_once()
