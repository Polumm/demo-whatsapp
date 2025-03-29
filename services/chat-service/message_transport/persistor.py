import json
from aio_pika import connect_robust, ExchangeType, Message, DeliveryMode
from typing import Optional
from aio_pika.abc import AbstractExchange

from config import RABBIT_HOST, RABBIT_PORT


_persistence_exchange: Optional[AbstractExchange] = None


async def send_to_persistence_queue(msg_data):
    global _persistence_exchange

    if not _persistence_exchange:
        connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)
        channel = await connection.channel()
        _persistence_exchange = await channel.declare_exchange(
            "persistence-exchange", ExchangeType.DIRECT, durable=True
        )

    body = json.dumps(msg_data).encode()
    await _persistence_exchange.publish(
        Message(body, delivery_mode=DeliveryMode.PERSISTENT),
        routing_key="store",
    )
