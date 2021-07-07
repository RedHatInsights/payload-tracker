import os
import logging
import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.helpers import create_ssl_context
from kafkahelpers import ReconnectingClient
import settings

logger = logging.getLogger(settings.APP_NAME)

TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')

CAFILEPATH = os.environ.get("KAFKA_SSL_CAFILE")
KAFKA_CONSUMER_CONFIGS = {
    "bootstrap_servers": os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092'),
    "group_id": os.environ.get('GROUP_ID', 'payload_tracker'),
    "security_protocol": os.environ.get('KAFKA_SECURITY_PROTOCOL', "PLAINTEXT").upper(),
    "ssl_context": create_ssl_context(cafile=CAFILEPATH) if CAFILEPATH else None,
    "sasl_mechanism": os.environ.get("KAFKA_SASL_MECHANISM", "").upper(),
    "sasl_plain_username": os.environ.get("KAFKA_SASL_USERNAME", ""),
    "sasl_plain_password": os.environ.get("KAFKA_SASL_PASSWORD", "")
}


class Consumer(AIOKafkaConsumer):

    def __init__(self, loop):
        super().__init__(TOPIC, loop=loop, **KAFKA_CONSUMER_CONFIGS)
        self.client = ReconnectingClient(self, 'consumer')

    async def teardown(self):
        try:
            logger.info('Disconnecting client from Kafka...')
            asyncio.get_event_loop()
        except Exception as err:
            logger.error(f'Failed to acquire event loop with error: {err}')
        else:
            await self.stop()

    async def run(self, worker):
        try:
            await self.client.run(worker)
        except asyncio.CancelledError:
            await self.teardown()


consumer = Consumer(asyncio.get_event_loop())
