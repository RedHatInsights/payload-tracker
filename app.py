import os
import datetime
import traceback

from aiokafka import AIOKafkaConsumer
from kafkahelpers import ReconnectingClient
from prometheus_client import start_http_server, Counter, Enum, Gauge, Histogram, Info
from concurrent.futures import ThreadPoolExecutor
import insights_connexion.app as app
from insights_connexion.app import asyncio

import tracker_logging

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
BOOTSTRAP_SERVERS = os.environ.get('BOOTSTRAP_SERVERS', 'localhost:9092')
GROUP_ID = os.environ.get('GROUP_ID', 'payload_tracker')
THREAD_POOL_SIZE = os.environ.get('THREAD_POOL_SIZE', 8)
PAYLOAD_TRACKER_TOPIC = os.environ.get('PAYLOAD_TRACKER_TOPIC', 'payload_tracker')

# Prometheus configuration
DISABLE_PROMETHEUS = True if os.environ.get('DISABLE_PROMETHEUS') == "True" else False
PROMETHEUS_PORT = os.environ.get('PROMETHEUS_PORT', 8000)

PAYLOAD_TRACKER_SERVICE_VERSION = Info(
    'payload_tracker_service_version',
    'Release and versioning information'
)

BUILD_NAME = os.getenv('OPENSHIFT_BUILD_NAME', 'dev')
BUILD_ID = os.getenv('OPENSHIFT_BUILD_COMMIT', 'dev')
BUILD_REF = os.getenv('OPENSHIFT_BUILD_REFERENCE', '')
BUILD_STABLE = "-stable" if BUILD_REF == "stable" else ""
if BUILD_ID and BUILD_ID != 'dev':
    BUILD_URL = ''.join(["https://console.insights-dev.openshift.com/console/",
                 "project/buildfactory/browse/builds/payload-tracker",
                 BUILD_STABLE, "/", BUILD_NAME, "?tab=logs"])
    COMMIT_URL = ("https://github.com/RedHatInsights/payload-tracker/"
                 "commit/" + BUILD_ID)
else:
    BUILD_URL = "dev"
    COMMIT_URL = "dev"
PAYLOAD_TRACKER_SERVICE_VERSION.info({'build_name': BUILD_NAME,
                              'build_commit': BUILD_ID,
                              'build_ref': BUILD_REF,
                              'build_url': BUILD_URL,
                              'commit_url': COMMIT_URL})

# Setup logging
logger = tracker_logging.initialize_logging()


# start thread pool executor and loop
logger.info("Starting thread pool executor and asyncio loop.")
executor = ThreadPoolExecutor(max_workers=int(THREAD_POOL_SIZE))
loop = asyncio.get_event_loop()
loop.set_default_executor(executor)

# setup consumer
kafka_consumer = AIOKafkaConsumer(
    PAYLOAD_TRACKER_TOPIC, loop=loop, bootstrap_servers=BOOTSTRAP_SERVERS,
    group_id=GROUP_ID
)
CONSUMER = ReconnectingClient(kafka_consumer, "consumer")


# Handle sigterms so process shuts down cleanly only after flushing messages to kafka
_sigterm_received = False


async def process_payload_status(json_msgs):
    for msg in json_msgs:
        logger.info(f"Processing payload status for {json_msg}")

        # sanitize the payload status
        sanitized_payload_status = {
            'service': json_msg['service'],
            'payload_id': json_msg['payload_id'],
            'status': json_msg['status']
        }
        for key in ['inventory_id', 'system_id', 'status', 'status_msg']:
            if key in json_msg:
                sanitized_payload_status[key] = json_msg[key]

        if 'date' in json_msg:
            sanitized_payload_status['date'] = json_msg['date']
        else:
            sanitized_payload_status['date'] = datetime.datetime.now()

        # insert into database


async def consume(client):
    data = await client.getmany()
    for tp, msgs in data.items():
        logger.info("Received messages: %s", msgs)
        loop.create_task(process_payload_status(msgs))
    await asyncio.sleep(0.1)


def start():
    try:
        # Log env vars / settings
        logger.info("Using LOG_LEVEL: %s", LOG_LEVEL)
        logger.info("Using BOOTSTRAP_SERVERS: %s", BOOTSTRAP_SERVERS)
        logger.info("Using GROUP_ID: %s", GROUP_ID)
        logger.info("Using THREAD_POOL_SIZE: %s", THREAD_POOL_SIZE)
        logger.info("Using PAYLOAD_TRACKER_TOPIC: %s", PAYLOAD_TRACKER_TOPIC)
        logger.info("Using DISABLE_PROMETHEUS: %s", DISABLE_PROMETHEUS)
        logger.info("Using PROMETHEUS_PORT: %s", PROMETHEUS_PORT)

        # start prometheus
        if not DISABLE_PROMETHEUS:
            logger.info('Starting Payload Tracker Prometheus Server')
            start_prometheus()

        # add consumer callbacks
        logger.info('Starting Kafka consumer for Payload status messages.')
        loop.create_task(CONSUMER.get_callback(consume)())

        # start the API endpoint and database connections
        logger.info('Starting Connexions App for REST API and Database.')
        app.start()

    except Exception:
        # Shut down loop
        loop.stop()


def submit_to_executor(executor, fn, *args, **kwargs):
    future = executor.submit(fn, *args, **kwargs)
    logger.info("Submitted to executor, future: %s", future)
    future.add_done_callback(on_thread_done)


def on_thread_done(future):
    try:
        future.result()
    except Exception:
        logger.exception("Future %s hit exception", future)


def start_prometheus():
    start_http_server(PROMETHEUS_PORT)


if __name__ == "__main__":
    logger.info('Starting Payload Tracker Service')
    start()