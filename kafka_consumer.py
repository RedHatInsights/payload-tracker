import os
import asyncio
from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient


BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:29092')
TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')


class Consumer(AIOKafkaConsumer):

    def __init__(self, loop):
        super().__init__(TOPIC, bootstrap_servers=BOOTSTRAP_SERVERS, loop=loop, group_id=GROUP_ID)
        self.client = ReconnectingClient(self, 'consumer')

    def get_client(self):
        return self.client


consumer = Consumer(asyncio.get_event_loop())
