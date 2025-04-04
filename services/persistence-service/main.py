import asyncio
import logging
from aio_pika import connect_robust, ExchangeType

from persistence import on_persistence_message, init_db
from config import RABBIT_HOST, RABBIT_PORT

EXCHANGE_NAME = "persistence-exchange"
QUEUE_NAME = "persistence-queue"

async def main():
    logging.basicConfig(level=logging.INFO)
    print("[persistence-service] Starting up...")

    # Ensure DB tables are created
    await init_db()

    connection = await connect_robust(host=RABBIT_HOST, port=RABBIT_PORT)
    channel = await connection.channel()

    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
    queue = await channel.declare_queue(QUEUE_NAME, durable=True)
    await queue.bind(exchange, routing_key="store")

    await queue.consume(on_persistence_message, no_ack=False)

    print(f"[persistence-service] Listening on queue: {QUEUE_NAME}")
    await asyncio.Future()  # Keeps service alive

if __name__ == "__main__":
    asyncio.run(main())
