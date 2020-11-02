import os
import logging
import asyncio
from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient
import settings

logger = logging.getLogger(settings.APP_NAME)

BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')
TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')


class Consumer(AIOKafkaConsumer):

    def __init__(self, loop):
        super().__init__(TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS,
            loop=loop, group_id=GROUP_ID, enable_auto_commit=False)
        self.client = ReconnectingClient(self, 'consumer')

    @property
    async def partition_lags(self):
        return {p: 0 if not self.highwater(p) else (
            self.highwater(p) - await self.position(p)) for p in self.assignment()}

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
